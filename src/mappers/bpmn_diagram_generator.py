from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import heapq
import json
import math
import shutil
import statistics
import subprocess
import textwrap

from src.domain import bpmn as bpmn_model
from src.domain.cfg import ControlFlowGraph, CFGNodeType, CFGEventType


class BPMNDiagramGenerator:
    START_X = 60
    START_Y = 60
    HORIZONTAL_SPACING = 110
    VERTICAL_SPACING = 65
    TASK_WIDTH = 170
    TASK_HEIGHT = 90
    MAX_TASK_HEIGHT = 240
    GATEWAY_WIDTH = GATEWAY_HEIGHT = 50
    EVENT_WIDTH = EVENT_HEIGHT = 36
    BLOCK_PADDING_LEFT = BLOCK_PADDING_RIGHT = 40
    BLOCK_PADDING_TOP = 60
    BLOCK_PADDING_BOTTOM = 40
    BLOCK_MIN_WIDTH = 280
    BLOCK_MIN_HEIGHT = 180
    COMPONENT_VERTICAL_SPACING = 90
    ROUTE_CLEARANCE = 16
    LAYOUT_ITERATIONS = 6
    GRAPHVIZ_TIMEOUT = 15

    @dataclass
    class LayoutNode:
        x: float
        y: float
        width: float
        height: float
        rank: int = 0

        @property
        def center_x(self):
            return self.x + self.width / 2

        @property
        def center_y(self):
            return self.y + self.height / 2

        @property
        def right(self):
            return self.x + self.width

        @property
        def bottom(self):
            return self.y + self.height

    @dataclass
    class LayoutResult:
        positions: dict = field(default_factory=dict)
        children: dict = field(default_factory=dict)
        routes: dict = field(default_factory=dict)
        labels: dict = field(default_factory=dict)
        engine: str = "native"

    @classmethod
    def generate(cls, process_id: str, cfg: ControlFlowGraph, *, engine="auto"):
        """engine: auto (dot when available), graphviz (required), or native."""
        layout = cls._compute_layout(cfg.nodes, cfg.edges, engine=engine)
        diagram = cls._create_diagram(process_id)
        cls._create_shapes(diagram, cfg.nodes, layout)
        cls._create_edges(diagram, cfg.nodes, cfg.edges, layout)
        return diagram

    @classmethod
    def _get_node_id(cls, value):
        return value if isinstance(value, str) else str(value.id)

    @classmethod
    def _is_block_node(cls, node):
        return node.node_type == CFGNodeType.BLOCK

    @classmethod
    def _is_gateway_node(cls, node):
        return node.node_type == CFGNodeType.GATEWAY

    @classmethod
    def _is_event_node(cls, node):
        return node.node_type in (CFGNodeType.EVENT, CFGNodeType.TIMER_EVENT)

    @classmethod
    def _is_start_node(cls, node):
        return getattr(node, "event_type", None) == CFGEventType.START

    @classmethod
    def _get_dimension(cls, node):
        if cls._is_gateway_node(node):
            return cls.GATEWAY_WIDTH, cls.GATEWAY_HEIGHT
        if cls._is_event_node(node):
            return cls.EVENT_WIDTH, cls.EVENT_HEIGHT
        if cls._is_block_node(node):
            return cls.BLOCK_MIN_WIDTH, cls.BLOCK_MIN_HEIGHT
        title = getattr(node, "title", None) or ""
        width = 210 if len(title) > 100 else cls.TASK_WIDTH
        lines = textwrap.wrap(title, width=max(20, int((width - 20) / 7)))
        return width, max(cls.TASK_HEIGHT, min(cls.MAX_TASK_HEIGHT, 24 + len(lines) * 15))

    @classmethod
    def _adjacency(cls, nodes, edges):
        pred = {n: set() for n in nodes}
        succ = {n: set() for n in nodes}
        for edge in edges.values():
            s, t = cls._get_node_id(edge.source), cls._get_node_id(edge.target)
            if s not in nodes or t not in nodes:
                raise ValueError(f"Edge {edge.id} crosses a CFG scope or has missing endpoints")
            pred[t].add(s)
            succ[s].add(t)
        return pred, succ

    @classmethod
    def _components(cls, nodes, edges):
        pred, succ = cls._adjacency(nodes, edges)
        remaining, result = set(nodes), []
        while remaining:
            first = min(remaining)
            seen, todo = set(), [first]
            while todo:
                n = todo.pop()
                if n in seen:
                    continue
                seen.add(n)
                todo.extend(sorted((pred[n] | succ[n]) - seen, reverse=True))
            remaining -= seen
            result.append(seen)

        def key(component):
            auxiliary = any(
                getattr(getattr(nodes[n], "temporal_constraint", None), "temporal_category", None)
                and getattr(nodes[n].temporal_constraint.temporal_category, "value", "") == "keep_alive_bound"
                for n in component)
            return auxiliary, not any(cls._is_start_node(nodes[n]) for n in component), min(component)
        return sorted(result, key=key)

    @classmethod
    def _compute_ranks(cls, nodes, edges):
        """Longest-path ranks; break feedback edges deterministically and terminate."""
        pred, succ = cls._adjacency(nodes, edges)
        pending = {n: len(pred[n]) for n in nodes}
        ranks, done = {n: 0 for n in nodes}, set()
        ready = [n for n in nodes if pending[n] == 0]
        heapq.heapify(ready)
        while len(done) < len(nodes):
            if not ready:
                # A cycle needs a feedback edge. Layout it without unbounded
                # rank propagation; backward arrows are routed outside nodes.
                heapq.heappush(ready, min(set(nodes) - done))
            n = heapq.heappop(ready)
            if n in done:
                continue
            done.add(n)
            for t in sorted(succ[n]):
                if t in done:
                    continue
                ranks[t] = max(ranks[t], ranks[n] + 1)
                pending[t] -= 1
                if pending[t] == 0:
                    heapq.heappush(ready, t)
        return ranks

    @classmethod
    def _compute_layout(cls, nodes, edges, *, engine="auto"):
        if engine not in ("auto", "graphviz", "native"):
            raise ValueError(f"Unknown layout engine: {engine}")
        cls._adjacency(nodes, edges)
        result = cls.LayoutResult()
        dimensions = {}
        for nid in sorted(nodes):
            node = nodes[nid]
            if cls._is_block_node(node):
                child = cls._compute_layout(node.nodes, node.edges, engine=engine)
                result.children[nid] = child
                dimensions[nid] = cls._compute_block_dimensions(child)
            else:
                dimensions[nid] = cls._get_dimension(node)
        y = float(cls.START_Y)
        for component in cls._components(nodes, edges):
            local_nodes = {n: nodes[n] for n in sorted(component)}
            local_edges = {eid: e for eid, e in sorted(edges.items()) if e.source.id in component}
            use_dot = engine != "native" and shutil.which("dot") is not None
            if engine == "graphviz" and not use_dot:
                raise RuntimeError("Graphviz dot is unavailable; use engine='native' or install Graphviz")
            if use_dot:
                try:
                    local = cls._dot_layout(local_nodes, local_edges, dimensions)
                except (subprocess.SubprocessError, OSError, ValueError, KeyError) as exc:
                    if engine == "graphviz":
                        raise RuntimeError("Graphviz layout failed") from exc
                    local = cls._native_layout(local_nodes, local_edges, dimensions)
            else:
                local = cls._native_layout(local_nodes, local_edges, dimensions)
            left, top, right, bottom = cls._bounds(local)
            cls._translate(local, cls.START_X - left, y - top)
            result.positions.update(local.positions)
            result.routes.update(local.routes)
            result.labels.update(local.labels)
            result.engine = local.engine
            y += bottom - top + cls.COMPONENT_VERTICAL_SPACING
        for nid, child in result.children.items():
            cls._place_child_layout(child, result.positions[nid])
        return result

    @classmethod
    def _bounds(cls, layout):
        boxes = [(p.x, p.y, p.right, p.bottom) for p in layout.positions.values()]
        boxes += [(p.x, p.y, p.right, p.bottom) for p in layout.labels.values()]
        points = [p for route in layout.routes.values() for p in route]
        boxes += [(x, y, x, y) for x, y in points]
        if not boxes:
            return 0, 0, 0, 0
        return min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)

    @classmethod
    def _translate(cls, layout, dx, dy):
        for p in list(layout.positions.values()) + list(layout.labels.values()):
            p.x += dx
            p.y += dy
        for eid, route in layout.routes.items():
            layout.routes[eid] = [(x + dx, y + dy) for x, y in route]
        # Subprocess descendants must move together with their parent.
        for child in layout.children.values():
            cls._translate(child, dx, dy)

    @classmethod
    def _compute_block_dimensions(cls, layout):
        left, top, right, bottom = cls._bounds(layout)
        return (max(cls.BLOCK_MIN_WIDTH, right - left + cls.BLOCK_PADDING_LEFT + cls.BLOCK_PADDING_RIGHT),
                max(cls.BLOCK_MIN_HEIGHT, bottom - top + cls.BLOCK_PADDING_TOP + cls.BLOCK_PADDING_BOTTOM))

    @classmethod
    def _place_child_layout(cls, child_layout, block_position):
        left, top, _, _ = cls._bounds(child_layout)
        cls._translate(child_layout, block_position.x + cls.BLOCK_PADDING_LEFT - left,
                       block_position.y + cls.BLOCK_PADDING_TOP - top)

    @classmethod
    def _edge_label(cls, edge):
        condition = getattr(edge, "execution_condition", None)
        return (getattr(condition, "description", None) or getattr(condition, "expression", None) or "").strip()

    @classmethod
    def _label_size(cls, text):
        lines = textwrap.wrap(text, 28) or [""]
        return min(200, max(65, max(len(line) for line in lines) * 6.5)), len(lines) * 15 + 6

    @classmethod
    def _dot_layout(cls, nodes, edges, dimensions):
        names = {n: f"n{i}" for i, n in enumerate(sorted(nodes))}
        gap = cls.HORIZONTAL_SPACING
        source = ['digraph G {', f'graph [rankdir=LR, splines=ortho, nodesep=0.9, ranksep={gap/72:.3f}, margin=0, ordering=out];',
                  'node [label="", fixedsize=true];', 'edge [arrowsize=0.7, fontsize=11, fontname="Arial"];']
        for nid in sorted(nodes):
            width, height = dimensions[nid]
            node = nodes[nid]
            shape = "diamond" if cls._is_gateway_node(node) else "circle" if cls._is_event_node(node) else "box"
            source.append(f'{names[nid]} [shape={shape}, width={width/72:.6f}, height={height/72:.6f}];')
        for i, (eid, edge) in enumerate(sorted(edges.items())):
            label = cls._edge_label(edge)
            xlabel = ' label=' + json.dumps('\n'.join(textwrap.wrap(label, 28))) if label else ''
            source.append(f'{names[edge.source.id]} -> {names[edge.target.id]} [id="e{i}"{xlabel}];')
        source.append('}')
        # stdin and an argv list avoid shell interpolation and temporary files.
        raw = subprocess.run(['dot', '-Tjson'], input='\n'.join(source), text=True,
                             capture_output=True, check=True, timeout=cls.GRAPHVIZ_TIMEOUT)
        data = json.loads(raw.stdout)
        height = float(data['bb'].split(',')[3])
        result = cls.LayoutResult(engine="graphviz")
        ranks = cls._compute_ranks(nodes, edges)
        by_name = {name: nid for nid, name in names.items()}
        for obj in data.get('objects', []):
            nid = by_name[obj['name']]
            x, y = map(float, obj['pos'].split(','))
            width, node_height = dimensions[nid]
            result.positions[nid] = cls.LayoutNode(x-width/2, height-y-node_height/2, width, node_height, ranks[nid])
        edge_ids = list(sorted(edges))
        for obj in data.get('edges', []):
            eid = edge_ids[int(obj['id'][1:])]
            points = next(op['points'] for op in obj['_draw_'] if op['op'] == 'b')
            route = [(float(x), height-float(y)) for x,y in points]
            tokens = obj.get('pos', '').split()
            end = next((token for token in tokens if token.startswith('e,')), None)
            if end:
                _, x, y = end.split(',')
                route.append((float(x), height-float(y)))
            result.routes[eid] = cls._simplify(route)
            text = cls._edge_label(edges[eid])
            if text and 'lp' in obj:
                x, y = map(float, obj['lp'].split(','))
                w, h = cls._label_size(text)
                result.labels[eid] = cls.LayoutNode(x-w/2, height-y-h/2, w, h)
        # dot is normally obstacle-free, but explicit bounds validation also
        # covers unusual port placement and subprocess-sized rectangles.
        routed = []
        for eid, edge in sorted(edges.items()):
            route = result.routes.get(eid)
            obstacles = [p for nid,p in result.positions.items() if nid not in (edge.source.id, edge.target.id)]
            gateway_port = (cls._is_gateway_node(nodes[edge.source.id])
                            or cls._is_gateway_node(nodes[edge.target.id]))
            if gateway_port or not route or any(cls._hits(a,b,p) for a,b in zip(route,route[1:]) for p in obstacles):
                result.routes[eid] = cls._route_edge(edge, nodes, result.positions, routed)
            routed += list(zip(result.routes[eid], result.routes[eid][1:]))
        cls._place_labels(edges, result)
        return result

    @classmethod
    def _native_layout(cls, nodes, edges, dimensions):
        ranks = cls._compute_ranks(nodes, edges)
        pred, succ = cls._adjacency(nodes, edges)
        layers = defaultdict(list)
        dims = dict(dimensions)
        for nid in sorted(nodes):
            layers[ranks[nid]].append(nid)
        # Virtual nodes keep long edges in their own lane across intermediate
        # ranks. They participate in ordering but never become BPMN elements.
        for i, edge in enumerate(sorted(edges.values(), key=lambda e:e.id)):
            s,t = edge.source.id,edge.target.id
            if ranks[t] <= ranks[s]+1:
                continue
            pred[t].discard(s);succ[s].discard(t)
            previous = s
            for rank in range(ranks[s]+1,ranks[t]):
                dummy = ("virtual",i,rank)
                ranks[dummy] = rank;dims[dummy]=(0,0)
                layers[rank].append(dummy);pred[dummy]={previous};succ[dummy]=set()
                succ[previous].add(dummy);previous=dummy
            succ[previous].add(t);pred[t].add(previous)
        centers = {}
        for layer in layers.values():
            y=0
            for n in layer:
                centers[n]=y+dims[n][1]/2
                y+=dims[n][1]+cls.VERTICAL_SPACING
        for _ in range(cls.LAYOUT_ITERATIONS):
            for forward in (True,False):
                for rank in sorted(layers, reverse=not forward):
                    neighbours=pred if forward else succ
                    desired={n:statistics.median([centers[a] for a in neighbours[n]]) if neighbours[n] else centers[n]
                             for n in layers[rank]}
                    layer=sorted(layers[rank],key=lambda n:(desired[n],str(n)))
                    layers[rank]=layer
                    placed={}
                    previous=None
                    for n in layer:
                        y=desired[n]
                        if previous is not None:
                            y=max(y,placed[previous]+dims[previous][1]/2+dims[n][1]/2+cls.VERTICAL_SPACING)
                        placed[n]=y;previous=n
                    offset=statistics.mean(desired[n]-placed[n] for n in layer)
                    centers.update({n:placed[n]+offset for n in layer})
        result=cls.LayoutResult()
        rank_gaps = defaultdict(lambda: cls.HORIZONTAL_SPACING)
        for edge in edges.values():
            label = cls._edge_label(edge)
            if label:
                rank = ranks[edge.source.id]
                rank_gaps[rank] = max(rank_gaps[rank], cls._label_size(label)[0] + 48)
        x=0
        for rank in sorted(layers):
            width=max(dims[n][0] for n in layers[rank])
            for nid in layers[rank]:
                if nid not in nodes:
                    continue
                w,h=dims[nid]
                result.positions[nid]=cls.LayoutNode(x+(width-w)/2,centers[nid]-h/2,w,h,rank)
            x+=width+rank_gaps[rank]
        routed=[]
        for eid,edge in sorted(edges.items()):
            result.routes[eid]=cls._route_edge(edge,nodes,result.positions,routed)
            routed+=list(zip(result.routes[eid],result.routes[eid][1:]))
        cls._place_labels(edges,result)
        return result

    @classmethod
    def _hits(cls,a,b,box,padding=0):
        left,top,right,bottom=box.x-padding,box.y-padding,box.right+padding,box.bottom+padding
        if abs(a[0]-b[0]) < 1e-6:
            return left+1e-6<a[0]<right-1e-6 and max(min(a[1],b[1]),top)<min(max(a[1],b[1]),bottom)-1e-6
        if abs(a[1]-b[1]) < 1e-6:
            return top+1e-6<a[1]<bottom-1e-6 and max(min(a[0],b[0]),left)<min(max(a[0],b[0]),right)-1e-6
        return True  # A routed edge must be orthogonal.

    @classmethod
    def _route_edge(cls,edge,nodes,positions,previous_segments=()):
        s,t=positions[edge.source.id],positions[edge.target.id]
        clearance=cls.ROUTE_CLEARANCE
        backwards=t.x<=s.x
        start=(s.right,s.center_y);finish=(t.x,t.center_y)
        start_stub=(s.right+clearance,s.center_y);end_stub=(t.x-clearance,t.center_y)
        if edge.source.id == edge.target.id:
            # A self-loop needs different attachment points and a visible
            # outer turn, rather than overlapping outbound/return segments.
            finish=(t.center_x,t.bottom)
            end_stub=(t.center_x,t.bottom+clearance)
        elif backwards:
            # Returning edges leave/enter the bottom side; reserve an outer
            # channel rather than drawing through the forward-flow tasks.
            start=(s.center_x,s.bottom);finish=(t.center_x,t.bottom)
            start_stub=(s.center_x,s.bottom+clearance);end_stub=(t.center_x,t.bottom+clearance)
        if not backwards:
            source_node, target_node = nodes[edge.source.id], nodes[edge.target.id]
            if cls._is_gateway_node(source_node) and len(source_node.outgoing) > 1:
                delta = t.center_y - s.center_y
                if abs(delta) > cls.EVENT_HEIGHT / 2:
                    port_y = s.y if delta < 0 else s.bottom
                    start = (s.center_x, port_y)
                    start_stub = (s.center_x, port_y + (-clearance if delta < 0 else clearance))
            if cls._is_gateway_node(target_node) and len(target_node.incoming) > 1:
                delta = s.center_y - t.center_y
                if abs(delta) > cls.EVENT_HEIGHT / 2:
                    port_y = t.y if delta < 0 else t.bottom
                    finish = (t.center_x, port_y)
                    end_stub = (t.center_x, port_y + (-clearance if delta < 0 else clearance))
        obstacles=[]
        for nid,p in positions.items():
            pad=0 if nid in (edge.source.id,edge.target.id) else clearance
            obstacles.append(cls.LayoutNode(p.x-pad,p.y-pad,p.width+2*pad,p.height+2*pad))
        xs={start_stub[0],end_stub[0]};ys={start_stub[1],end_stub[1]}
        for p in obstacles:
            xs.update((p.x,p.right));ys.update((p.y,p.bottom))
        xs.update((min(xs)-clearance*2,max(xs)+clearance*2))
        ys.update((min(ys)-clearance*2,max(ys)+clearance*2))
        xs,ys=sorted(xs),sorted(ys)
        origin=(xs.index(start_stub[0]),ys.index(start_stub[1]),0)
        goal=(xs.index(end_stub[0]),ys.index(end_stub[1]))
        distance={origin:0};parent={};queue=[(0,0,origin)]
        while queue:
            _,cost,state=heapq.heappop(queue)
            if cost != distance.get(state):
                continue
            i,j,direction=state
            if (i,j)==goal:
                path=[(xs[i],ys[j])]
                while state!=origin:
                    state=parent[state];path.append((xs[state[0]],ys[state[1]]))
                return cls._simplify([start]+list(reversed(path))+[finish])
            a=(xs[i],ys[j])
            for ni,nj,nd in ((i-1,j,1),(i+1,j,1),(i,j-1,2),(i,j+1,2)):
                if not (0<=ni<len(xs) and 0<=nj<len(ys)):
                    continue
                b=(xs[ni],ys[nj])
                if any(cls._hits(a,b,p) for p in obstacles):
                    continue
                step=abs(a[0]-b[0])+abs(a[1]-b[1])+(28 if direction and direction!=nd else 0)
                # Prefer routes with fewer crossings.
                for c,d in previous_segments:
                    if cls._crosses(a,b,c,d):
                        step+=120
                new=(ni,nj,nd);new_cost=cost+step
                if new_cost>=distance.get(new,math.inf):
                    continue
                distance[new]=new_cost;parent[new]=state
                heuristic=abs(b[0]-end_stub[0])+abs(b[1]-end_stub[1])
                heapq.heappush(queue,(new_cost+heuristic,new_cost,new))
        raise ValueError(f"Cannot route edge {edge.id} without crossing a node")

    @staticmethod
    def _crosses(a,b,c,d):
        if a[1]==b[1] and c[0]==d[0]:
            return min(a[0],b[0])<c[0]<max(a[0],b[0]) and min(c[1],d[1])<a[1]<max(c[1],d[1])
        if a[0]==b[0] and c[1]==d[1]:
            return min(c[0],d[0])<a[0]<max(c[0],d[0]) and min(a[1],b[1])<c[1]<max(a[1],b[1])
        return False

    @staticmethod
    def _simplify(points):
        result=[]
        for point in points:
            point=tuple(float(v) for v in point)
            if result and point==result[-1]:
                continue
            if len(result)>=2:
                a,b=result[-2:]
                if (abs(a[0]-b[0])<1e-6 and abs(b[0]-point[0])<1e-6) or (abs(a[1]-b[1])<1e-6 and abs(b[1]-point[1])<1e-6):
                    # Only remove collinear points when movement does not
                    # reverse direction (feedback loops may double back).
                    if (b[0]-a[0])*(point[0]-b[0])+(b[1]-a[1])*(point[1]-b[1])>=0:
                        result.pop()
            result.append(point)
        return result

    @classmethod
    def _place_labels(cls,edges,layout):
        occupied=list(layout.positions.values())
        for eid,edge in sorted(edges.items()):
            text=cls._edge_label(edge)
            if not text:
                continue
            w,h=cls._label_size(text)
            old=layout.labels.get(eid)
            candidates=[old] if old else []
            route=layout.routes[eid]
            segments=sorted(zip(route,route[1:]),key=lambda ab:-(abs(ab[0][0]-ab[1][0])+abs(ab[0][1]-ab[1][1])))
            for a,b in segments:
                x,y=(a[0]+b[0])/2,(a[1]+b[1])/2
                if abs(a[1]-b[1])<1e-6:
                    candidates += [cls.LayoutNode(x-w/2,y-h-8,w,h),cls.LayoutNode(x-w/2,y+8,w,h)]
                else:
                    candidates += [cls.LayoutNode(x+8,y-h/2,w,h),cls.LayoutNode(x-w-8,y-h/2,w,h)]
            candidates=[p for p in candidates if p is not None]
            # Reserve the label beside its flow, including space for long
            # condition text; avoid covering a different sequence flow.
            chosen=next((p for p in candidates
                         if not any(cls._boxes_overlap(p,o,6) for o in occupied)
                         and not any(cls._hits(a,b,p,3) for other in layout.routes.values()
                                     for a,b in zip(other,other[1:]))),None)
            if chosen is None:
                # Extend the component bounds to reserve a clean label area.
                left,top,right,bottom=cls._bounds(layout)
                chosen=cls.LayoutNode(route[0][0],bottom+16,w,h)
            layout.labels[eid]=chosen;occupied.append(chosen)

    @staticmethod
    def _boxes_overlap(a,b,gap=0):
        return a.x<b.right+gap and b.x<a.right+gap and a.y<b.bottom+gap and b.y<a.bottom+gap

    @classmethod
    def _create_diagram(cls,process_id):
        return bpmn_model.Bpmndiagram(id=f"{process_id}_diagram",bpmnplane=bpmn_model.Bpmnplane(
            id=f"{process_id}_plane",bpmn_element=process_id))

    @classmethod
    def _create_shapes(cls,diagram,nodes,layout):
        for nid,p in sorted(layout.positions.items()):
            shape=bpmn_model.Bpmnshape(id=f"{nid}_shape",bpmn_element=nid,
                    bounds=bpmn_model.Bounds(x=p.x,y=p.y,width=p.width,height=p.height))
            if cls._is_block_node(nodes[nid]):
                shape.is_expanded=True
            diagram.bpmnplane.bpmnshape.append(shape)
            if nid in layout.children:
                cls._create_shapes(diagram,nodes[nid].nodes,layout.children[nid])

    @classmethod
    def _create_edges(cls,diagram,nodes,edges,layout):
        for eid,route in sorted(layout.routes.items()):
            di_edge=bpmn_model.Bpmnedge(id=f"{eid}_edge",bpmn_element=eid,
                        waypoint=[bpmn_model.Point(x=x,y=y) for x,y in route])
            if eid in layout.labels:
                p=layout.labels[eid]
                di_edge.bpmnlabel=bpmn_model.Bpmnlabel(bounds=bpmn_model.Bounds(x=p.x,y=p.y,width=p.width,height=p.height))
            diagram.bpmnplane.bpmnedge.append(di_edge)
        for nid,child in sorted(layout.children.items()):
            cls._create_edges(diagram,nodes[nid].nodes,nodes[nid].edges,child)

    @classmethod
    def _compute_edge_waypoints(cls,source,target):
        """Compatibility helper; generate() uses the obstacle-aware scope router."""
        if abs(source.center_y-target.center_y)<1e-6 and target.x>source.right:
            return [(source.right,source.center_y),(target.x,target.center_y)]
        if target.x>source.right:
            x=(source.right+target.x)/2
            return cls._simplify([(source.right,source.center_y),(x,source.center_y),(x,target.center_y),(target.x,target.center_y)])
        y=max(source.bottom,target.bottom)+cls.ROUTE_CLEARANCE*2
        return cls._simplify([(source.center_x,source.bottom),(source.center_x,y),(target.center_x,y),(target.center_x,target.bottom)])
