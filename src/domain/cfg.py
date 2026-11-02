from src.utils.definition_identifiers import action_definition_id
from src.domain.temporal_constraint import TemporalConstraint
from dataclasses import dataclass
from src.domain.enums import TemporalCategory
from src.domain.exceptions import ContractIdException, PlanDefinitionValidationException, RequestOrchestrationValidationException
from fhir.resources.plandefinition import PlanDefinition, PlanDefinitionAction
from fhir.resources.requestorchestration import RequestOrchestration, RequestOrchestrationAction
from src.domain.nodes import (
    CFGNode,
    CFGEdge,
    FHIRExecutionCondition,
    ActionNode,
    CFGGatewayClass,
    CFGGatewayDirection,
    GatewayNode,
    CFGEventType,
    EventNode,
    TimerEventNode,
    BlockNode,
    FakeNode
)
from src.domain.temporal_constraint import FHIRTemporalConstraint
from src.domain.enums import FHIRRelationshipType, CFGNodeType, CFGType
from typing import Any, Dict, List, Optional, Set, Type, Union
import re
from urllib.parse import urlsplit

class SESERegion:
    """
    Represents a Single-Entry Single-Exit region in the control flow graph.
    """

    entry: CFGNode
    """Entry node of the region. Corresponds to the entry node in the sequence."""
    exit: CFGNode
    """Exit node of the region. Corresponds to the exit node in the sequence."""
    body: set[CFGNode]
    """Set of nodes in the region. Corresponds to all nodes in the sequence."""

    def __init__(self, entry: CFGNode, exit: CFGNode, body: Set[CFGNode]):
        self.entry = entry
        self.exit = exit
        self.body = body

    def nodes(self) -> Set[CFGNode]:
        """
        Returns the set of all nodes in the region, including the entry and exit nodes.

        :return: Set of nodes in the region.
        :rtype: Set[CFGNode]
        """
        return self.body.union({self.entry, self.exit})

    def contains(self, other_region: "SESERegion") -> bool:
        """
        Checks if the current region contains another region.

        :param other_region: The other region to check.
        :type other_region: SESERegion
        :return: True if the current region contains the other region, False otherwise.
        :rtype: bool
        """
        return other_region.nodes().issubset(self.nodes())

    def size(self) -> int:
        """
        Returns the size of the region, defined as the number of nodes in the region.

        :return: Size of the region.
        :rtype: int
        """
        return len(self.nodes())

    def validate(self) -> bool:
        """
        Validates the region, checking if it is a valid single-entry single-exit region.

        :return: True if the region is valid, False otherwise.
        :rtype: bool
        """
        for n in self.nodes():
            for e in n.incoming:
                if e.source not in self.nodes() and n != self.entry:
                    return False
        for n in self.nodes():
            for e in n.outgoing:
                if e.target not in self.nodes() and n != self.exit:
                    return False
        return True

    def edges(self) -> Dict[str, CFGEdge]:
        """
        Returns the set of all edges in the region, including edges entering the region and edges exiting the region.

        :return: Set of edges in the region.
        :rtype: Dict[str, CFGEdge]
        """
        edges = {}
        for node in self.body:
            for e in node.incoming:
                if e.id not in edges:
                    edges[e.id] = e
            for e in node.outgoing:
                if e.id not in edges:
                    edges[e.id] = e
        for e in self.entry.outgoing:
            if e.id not in edges:
                edges[e.id] = e
        for e in self.exit.incoming:
            if e.id not in edges:
                edges[e.id] = e
        return edges

    def to_subgraph(self) -> "ControlFlowGraph":
        """
        Creates a new ControlFlowGraph from the nodes and edges in the SESE region.

        :return: ControlFlowGraph that represents the SESE region.
        :rtype: ControlFlowGraph
        """
        cfg = ControlFlowGraph(
            cfg_type=CFGType.GATEWAY,
            id=f"sese_subgraph_{self.entry.id}-{self.exit.id}",
            name=f"sese_subgraph_{self.entry.id}-{self.exit.id}",
            version="*",
            title=f"SESE Region Subgraph ({self.entry.id}-{self.exit.id})",
            description=f"SESE Region Subgraph ({self.entry.id}-{self.exit.id})",
        )
        cfg.add_node(
            self.entry.clone(),
            start=True
        )
        cfg.add_node(
            self.exit.clone(),
            end=True
        )
        for n in self.body:
            cfg.add_node(n.clone())
        for e in self.edges().values():
            cfg.add_edge(
                src=e.source.id,
                tgt=e.target.id,
                execution_condition=e.execution_condition,
                relationship=e.relationship
            )

        return cfg

    def is_maximal(self, cfg: "ControlFlowGraph") -> bool:
        """
        Checks if the SESE region is maximal, i.e., if it is the entire ControlFlowGraph.

        :param cfg: The ControlFlowGraph of which the SESE region is a part of.
        :type cfg: ControlFlowGraph
        :return: True if the SESE region is maximal, False otherwise.
        :rtype: bool
        """
        return (
            self.entry == cfg.start_node
            and self.exit == cfg.end_node
            and self.nodes() == set(cfg.nodes.values())
        )

    def __str__(self):
        return f'Region(start="{self.entry.id}", end="{self.exit.id}", body=["{'", "'.join([n.id for n in self.body])}"])'

class CFGFragment:
    """
    Represents a fragment of a control flow graph, which is a subgraph of a control flow graph.
    """
    
    start_node : Optional[CFGNode]
    """Starting node of the fragment."""
    end_node : Optional[CFGNode]
    """Ending node of the fragment."""
    nodes : Dict[str, CFGNode]
    """Set of all nodes in the fragment."""
    edges : Dict[str, CFGEdge]
    """Map of all edges in the fragment, with edge identifier as key and CFGEdge instance as value."""

    def __init__(self):
        self.nodes = {}
        self.edges = {}
    
    def add_node(self, node: CFGNode, start: bool = False, end: bool = False):
        """
        Adds a node to the fragment.

        :param node: The node to add.
        :type node: CFGNode
        :param start: Whether the node is the starting node of the fragment.
        :type start: bool
        :param end: Whether the node is the ending node of the fragment.
        :type end: bool
        """
        if node.id not in self.nodes:    
            self.nodes[node.id] = node.clone()
            if start:
                self.start_node = self.nodes[node.id]
            if end:
                self.end_node = self.nodes[node.id]
    
    def add_edge(
        self, 
        src: str, 
        tgt: str, 
        relationship: FHIRRelationshipType,
        execution_condition: Optional[FHIRExecutionCondition] = None
    ) -> Optional[CFGEdge]:
        """
        Adds an edge to the control flow graph.

        :param src: Source node identifier.
        :type src: str
        :param tgt: Target node identifier.
        :type tgt: str
        :param execution_condition: Edge condition.
        :type execution_condition: Optional[FHIRExecutionCondition]
        :return: CFGEdge instance if the edge was added, None otherwise.
        :rtype: Optional[CFGEdge]
        """
        e_id = src + "_to_" + tgt
        if src in self.nodes and tgt in self.nodes and e_id not in self.edges:
            s = self.nodes.get(src)
            t = self.nodes.get(tgt)
            e = CFGEdge(source=s, target=t, relationship=relationship, execution_condition=execution_condition)
            self.edges[e_id] = e
            if s is None:
                # TODO Custom Exception
                raise ValueError("Source node not found.")
            if t is None:
                # TODO Custom Exception
                raise ValueError("Target node not found.")
            s.outgoing.append(e)
            t.incoming.append(e)
            return e

    def clone_edge(self, edge: CFGEdge):
        """
        Adds an edge to the fragment.

        :param edge: The edge to add.
        :type edge: CFGEdge
        :param start: Whether the edge is the starting edge of the fragment.
        :type start: bool
        :param end: Whether the edge is the ending edge of the fragment.
        :type end: bool
        """
        if edge.id not in self.edges:
            new_edge = edge.clone()
            source = edge.source
            target = edge.target

            new_edge.source = self.nodes[source.id]
            new_edge.target = self.nodes[target.id]
            self.edges[edge.id] = new_edge
            self.nodes[source.id].outgoing.append(new_edge)
            self.nodes[target.id].incoming.append(new_edge)
    
    def to_cfg(self, id: str, version: str, name: str, title: str, description: str,) -> "ControlFlowGraph":
        cfg = ControlFlowGraph(
            cfg_type=CFGType.GATEWAY,
            id=id,
            version=version,
            name=name,
            title=title,
            description=description
        )
        for node in self.nodes.values():
            cfg.add_node(
                node=node.clone(),
                start=node.id == self.start_node.id if self.start_node else False,
                end=node.id == self.end_node.id if self.end_node else False,
            )
        for edge in self.edges.values():
            cfg.add_edge(
                src=edge.source.id,
                tgt=edge.target.id,
                execution_condition=edge.execution_condition,
                relationship=edge.relationship
            )
        return cfg
    
    @staticmethod
    def merge(fragments : List["CFGFragment"]) -> "CFGFragment":
        merged = CFGFragment()

        # 1. Add all fragments elements in the same CFGFragment
        for f in fragments:
            for node in f.nodes.values():
                merged.add_node(node)
            for edge in f.edges.values():
                merged.clone_edge(edge)
        
        # 2. Identification all start and end elements
        start_elements = {f.start_node.id : f.start_node for f in fragments if f.start_node}
        start_elements_ids = {node.id for node in start_elements.values()}
        end_elements = {f.end_node.id : f.end_node for f in fragments if f.end_node}
        end_elements_ids = {node.id for node in end_elements.values()}

        # Case 1: Merging parallel fragments (same start node and same end node)
        if len(start_elements_ids) == 1 and len(end_elements_ids) == 1:
            merged.start_node = start_elements[start_elements_ids.pop()]
            merged.end_node = end_elements[end_elements_ids.pop()]
            return merged
        
        # Case 2: Merging sequential fragments (end node corresponds to start node
        start_candidates = start_elements_ids - end_elements_ids
        end_candidates = end_elements_ids - start_elements_ids

        if len(start_candidates) == 1 and len(end_candidates) == 1:
            merged.start_node = start_elements[start_candidates.pop()]
            merged.end_node = end_elements[end_candidates.pop()]
            return merged
        
        # TODO Custom Exception
        raise ValueError("Fragments cannot be merged")

class ControlFlowGraph:
    """
    Represents a control flow graph structure of the clinical pathway.
    It contains nodes and edges, defined from a FHIR PlanDefinition resource or derived from them.
    """

    cfg_type: CFGType
    """Clinical pathway graph type."""
    id: str
    """Clinical pathway graph identifier. Corresponds to 'id' field in FHIR PlanDefinition."""
    name: str
    """Clinical pathway machine-readable name. Corresponds to 'name' field in FHIR PlanDefinition."""
    title: str
    """Clinical pathway human-readable title. Corresponds to 'title' field in FHIR PlanDefinition."""
    description: str
    """Clinical pathway human-readable description. Corresponds to 'description' field in FHIR PlanDefinition."""
    version: str
    """Clinical pathway version. Corresponds to 'version' field in FHIR PlanDefinition."""
    nodes: Dict[str, CFGNode]
    """Map of all nodes in the clinical pathway graph, with node identifier as key and CFGNode instance as value."""
    edges: Dict[str, CFGEdge]
    """Map of all edges in the clinical pathway graph, with edge identifier as key and CFGEdge instance as value."""
    start_node: Optional[CFGNode]
    """Starting node of the graph."""
    end_node: Optional[CFGNode]
    """Ending node of the graph."""

    def __init__(
        self,
        cfg_type: CFGType,
        id: str,
        version: str,
        title: str,
        name: str,
        description: str,
    ):
        self.cfg_type = cfg_type
        self.id = id
        self.version = version
        self.title = title
        self.name = name
        self.description = description
        self.nodes = {}
        self.edges = {}
        self.start_node = None
        self.end_node = None

    def add_node(self, node: CFGNode, start: bool = False, end : bool = False) -> Optional[CFGNode]:
        if node.id not in self.nodes:
            self.nodes[node.id] = node
            if start:
                self.start_node = node
            if end:
                self.end_node = node
            return node

    def add_edge(
        self, 
        src: str, 
        tgt: str, 
        relationship: FHIRRelationshipType,
        execution_condition: Optional[FHIRExecutionCondition] = None
    ) -> Optional[CFGEdge]:
        """
        Adds an edge to the control flow graph.

        :param src: Source node identifier.
        :type src: str
        :param tgt: Target node identifier.
        :type tgt: str
        :param execution_condition: Edge condition.
        :type execution_condition: Optional[FHIRExecutionCondition]
        :return: CFGEdge instance if the edge was added, None otherwise.
        :rtype: Optional[CFGEdge]
        """
        e_id = src + "_to_" + tgt
        if src in self.nodes and tgt in self.nodes and e_id not in self.edges:
            s = self.nodes.get(src)
            t = self.nodes.get(tgt)
            e = CFGEdge(source=s, target=t, relationship=relationship, execution_condition=execution_condition)
            self.edges[e_id] = e
            if s is None:
                # TODO Custom Exception
                raise ValueError("Source node not found.")
            if t is None:
                # TODO Custom Exception
                raise ValueError("Target node not found.")
            s.outgoing.append(e)
            t.incoming.append(e)
            return e

    def get_node(self, node_id: str) -> Optional[CFGNode]:
        """
        Return a node of the control flow graph with the given ID, if it exists.
        
        :param node_id: Node identifier.
        :type node_id: str
        :return: CFGNode if the node exists, None otherwise.
        :rtype: Optional[CFGNode]
        """
        node = self.nodes.get(node_id)
        if node is None:
            for n in self.nodes.values():
                if n.node_type == CFGNodeType.BLOCK:
                    node = n.nodes.get(node_id)
                    if node is not None:
                        break
        return node

    def dominators(self) -> Dict[CFGNode, Set[CFGNode]]:
        """
        Calculates the dominators of each node in the control flow graph.

        :return: Dictionary mapping each node to its dominators.
        :rtype: Dict[CFGNode, Set[CFGNode]]
        """
        nodes = set(self.nodes.values())
        start = self.start_node
        if start is None:
            # TODO Custom Exception
            raise ValueError("Start node not found.")

        dom: Dict[CFGNode, Set[CFGNode]] = {}
        for n in nodes:
            dom[n] = set(nodes)
        dom[start] = {start}

        changed = True
        while changed:
            changed = False
            for n in nodes:
                if n == start:
                    continue
                preds = [e.source for e in n.incoming]
                if not preds:
                    continue
                new_dom = set(nodes)
                for p in preds:
                    new_dom &= dom[p]

                new_dom.add(n)

                if new_dom != dom[n]:
                    dom[n] = new_dom
                    changed = True
        return dom

    def postdominators(self) -> Dict[CFGNode, Set[CFGNode]]:
        """
        Calculates the post-dominators of each node in the control flow graph.

        :return: Dictionary mapping each node to its post-dominators.
        :rtype: Dict[CFGNode, Set[CFGNode]]
        """
        nodes = set(self.nodes.values())
        end = self.end_node
        if end is None:
            # TODO Custom Exception
            raise ValueError("End node not found.")

        postdom = {}
        for n in nodes:
            postdom[n] = set(nodes)
        postdom[end] = {end}

        changed = True
        while changed:
            changed = False
            for n in nodes:
                if n == end:
                    continue

                succs = [e.target for e in n.outgoing]
                if not succs:
                    continue

                new_pd = set(nodes)
                for s in succs:
                    new_pd &= postdom[s]

                new_pd.add(n)

                if new_pd != postdom[n]:
                    postdom[n] = new_pd
                    changed = True

        return postdom

    def sese_regions(self) -> list[SESERegion]:
        """
        Extracts Single-Entry Single-Exit (SESE) regions from the control flow graph.

        :return: List of SESE regions found in the graph.
        :rtype: list[SESERegion]
        """
        dom = self.dominators()
        postdom = self.postdominators()

        sese_regions = []

        for x in self.nodes.values():
            for y in self.nodes.values():
                if x == y:
                    continue

                if x in dom[y] and y in postdom[x]:
                    region_body = set()
                    for n in self.nodes.values():
                        if x in dom[n] and y in postdom[n]:
                            if (
                                x != n and y != n
                            ):  # Aggiungo solo i nodi del body
                                region_body.add(n)
                    region = SESERegion(entry=x, exit=y, body=region_body)
                    if region.validate():
                        sese_regions.append(region)
        return sese_regions

    def subgraph(self, start: str, end: str) -> "ControlFlowGraph":
        """
        Extracts a subgraph from the control flow graph.

        :param start: Start node identifier.
        :type start: str
        :param end: End node identifier.
        :type end: str
        :return: Subgraph.
        :rtype: ControlFlowGraph
        """
        def _reachable_from(start: CFGNode) -> Set[str]:
            visited = set()
            stack = [start]

            while stack:
                node = stack.pop()
                if node.id in visited:
                    continue
                visited.add(node.id)
                for e in node.outgoing:
                    stack.append(e.target)

            return visited

        def _can_reach(end: CFGNode) -> Set[str]:
            visited = set()
            stack = [end]

            while stack:
                node = stack.pop()
                if node.id in visited:
                    continue
                visited.add(node.id)
                for e in node.incoming:
                    stack.append(e.source)

            return visited

        # Start and end nodes check
        if start not in self.nodes or end not in self.nodes:
            # TODO custom Exception
            raise ValueError(f"Start node {start} or end node {end} not found")
        start_node = self.nodes[start]
        end_node = self.nodes[end]

        forward = _reachable_from(start_node)
        backward = _can_reach(end_node)
        sub_nodes_ids = forward.intersection(backward)
        if start not in sub_nodes_ids or end not in sub_nodes_ids:
            # TODO custom Exception
            raise ValueError(f"Start node {start} or end node {end} not reachable")

        sub = ControlFlowGraph(
            cfg_type=self.cfg_type,
            id=f"{self.id}_sub_{start}_{end}",
            version=self.version,
            name=self.name,
            title=self.title,
            description=f"Subgraph of {self.name} from {start} to {end}",
        )
        for nid in sub_nodes_ids:
            node = self.nodes[nid]
            sub.add_node(node.clone())
        for edge in self.edges.values():
            s_id = edge.source.id
            t_id = edge.target.id
            if s_id in sub_nodes_ids and t_id in sub_nodes_ids:
                sub.add_edge(
                    src=s_id,
                    tgt=t_id,
                    execution_condition=edge.execution_condition,
                    relationship=edge.relationship,
                )
        return sub

    def sese_region_tree(self) -> dict[SESERegion, list[SESERegion]]:
        """
        Builds a tree of Single-Entry Single-Exit (SESE) regions from the control flow graph.

        :return: Tree of SESE regions.
        :rtype: dict[SESERegion, list[SESERegion]]
        """
        regions = self.sese_regions()

        # 1. containment check
        tree: dict[SESERegion, list[SESERegion]] = {r: [] for r in regions}
        for r1 in regions:
            for r2 in regions:
                if r1 != r2 and r1.contains(r2):
                    tree[r1].append(r2)

        # 2. transitive reduction
        direct_tree: dict[SESERegion, list[SESERegion]] = {
            r: [] for r in regions
        }

        for parent in regions:
            for child in tree[parent]:
                is_direct = True
                for middle in tree[parent]:
                    if middle == child:
                        continue
                    if middle.contains(child):
                        is_direct = False
                        break
                if is_direct:
                    direct_tree[parent].append(child)

        return direct_tree

    def remove_node(self, id: str, keep_edges: bool = False) -> Optional[CFGNode]:
        """
        Removes a node from the control flow graph and all associated edges.
        If keep_edges is True, the edges connected to the node remain in 
        incoming and outcoming lists of the edge source and target nodes, but 
        they are always removed from graph.
        If keep_edges is False, the edges connected to the node are always 
        removed also from incoming and outcoming lists of the edge source and 
        target nodes.

        :param id: Node identifier.
        :type id: str
        :param keep_edges: Whether to keep the edges connected to the node.
        :type keep_edges: bool
        :return: The removed node, None if not found.
        :rtype: Optional[CFGNode]
        """
        if id not in self.nodes:
            return None
        
        node = self.nodes.pop(id)

        if not keep_edges:
            for e in node.incoming:
                self.remove_edge(e.id)
            for e in node.outgoing:
                self.remove_edge(e.id)
        else:
            for e in node.incoming:
                self.edges.pop(e.id, None)
            for e in node.outgoing:
                self.edges.pop(e.id, None)

        return node
    
    def remove_edge(self, id: str) -> bool:
        """
        Removes an edge from the control flow graph and from the incoming and outcoming 
        lists of the edge source and target nodes.

        :param id: Edge identifier.
        :type id: str
        :return: True if the edge was removed, False otherwise.
        :rtype: bool
        """
        if id not in self.edges:
            return False
        
        edge = self.edges.pop(id)
        edge.source.outgoing.remove(edge)
        edge.target.incoming.remove(edge)
        return True

    def replace_end_node(self, node: CFGNode):
        """
        Replaces the end node of the control flow graph.

        :param node: New end node.
        :type node: CFGNode
        :param attributes: New end node attributes.
        :type attributes: Optional[dict[str, str]]
        """
        old_end = self.end_node
        if old_end is None:
            # TODO Custom Exception
            raise ValueError("End node not found.")

        edge_to_remove = list(old_end.incoming)

        for e in edge_to_remove:
            e.source.outgoing.remove(e)
            old_end.incoming.remove(e)
            del self.edges[e.id]

        del self.nodes[old_end.id]

        self.add_node(node)
        for e in edge_to_remove:
            self.add_edge(src=e.source.id, tgt=node.id, relationship=e.relationship, execution_condition=e.execution_condition)

    def find_all_bound_paths(self, start_node: ActionNode) -> List[List[str]]:
        """
        Find all paths starting from a given node until an unpaired
        convergent gateway or an end event node.

        :param start_node: The node to start from.
        :type start_node: ActionNode
        :return: List of paths.
        :rtype: List[List[str]]
        """

        @dataclass
        class PathState:
            path: List[str]
            gateway_depth: int

        def extend_path(path: List[str], node_id: str) -> List[str]:
            new_path = path.copy()
            new_path.append(node_id)
            return new_path

        path_stack = [
            PathState(
                path=[start_node.id],
                gateway_depth=0
            )
        ]

        completed_paths: List[List[str]] = []

        while path_stack:
            state = path_stack.pop()

            current_node: CFGNode = self.nodes[state.path[-1]]

            successors: List[CFGNode] = [
                edge.target for edge in current_node.outgoing
            ]

            for successor in successors:

                # End event
                if (
                    successor.node_type == CFGNodeType.EVENT
                    and successor.event_type == CFGEventType.END
                ):
                    completed_paths.append(state.path.copy())

                # Gateway
                elif successor.node_type == CFGNodeType.GATEWAY:

                    # Convergent gateway
                    if (
                        successor.gateway_direction
                        == CFGGatewayDirection.CONVERGENT
                    ):

                        # Boundary-event convergent gateway
                        if "conv_bound" in successor.id:
                            path_stack.append(
                                PathState(
                                    path=extend_path(
                                        state.path,
                                        successor.id
                                    ),
                                    gateway_depth=state.gateway_depth
                                )
                            )

                        # Unpaired convergent gateway:
                        # path terminates here
                        elif state.gateway_depth == 0:
                            completed_paths.append(
                                state.path.copy()
                            )

                        # Paired convergent gateway:
                        else:
                            path_stack.append(
                                PathState(
                                    path=extend_path(
                                        state.path,
                                        successor.id
                                    ),
                                    gateway_depth=state.gateway_depth - 1
                                )
                            )

                    # Divergent gateway
                    else:
                        path_stack.append(
                            PathState(
                                path=extend_path(
                                    state.path,
                                    successor.id
                                ),
                                gateway_depth=state.gateway_depth + 1
                            )
                        )

                # Normal node
                else:
                    path_stack.append(
                        PathState(
                            path=extend_path(
                                state.path,
                                successor.id
                            ),
                            gateway_depth=state.gateway_depth
                        )
                    )

        return completed_paths

    def to_json(self) -> Dict[str, Any]:
        """
        Convert the Control Flow Graph to a JSON object.

        :return: JSON object representing the Control Flow Graph.
        :rtype: Dict[str, Any]
        """
        obj : Dict[str, Any] = {
            "cfg_type": self.cfg_type.value,
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "name": self.name,
            "description": self.description,
            "start_node": self.start_node.id if self.start_node else None,
            "end_node": self.end_node.id if self.end_node else None,
            "nodes": {},
            "edges": {},
        }
        for node in self.nodes.values():
            obj["nodes"][node.id] = node.to_json()
        for edge in self.edges.values():
            obj["edges"][edge.id] = edge.to_json()

        return obj

class InstanceControlFlowGraph(ControlFlowGraph):
    subject_id : str
    request_orchestration_id : str

    def __init__(self,
        cfg_type: CFGType,
        id: str,
        version: str,
        title: str,
        name: str,
        description: str,
        subject_id: str,
        request_orchestration_id: str,
    ):
        super().__init__(cfg_type, id, version, title, name, description)
        self.subject_id = subject_id
        self.request_orchestration_id = request_orchestration_id

    def to_json(self) -> Dict[str, Any]:
        """
        Serialize the graph together with its instance-level origin.

        :return: CFG payload retaining patient and RequestOrchestration identifiers.
        :rtype: Dict[str, Any]
        """
        payload = super().to_json()
        payload.update(
            graph_type="instance",
            subject_id=self.subject_id,
            request_orchestration_id=self.request_orchestration_id,
        )
        return payload

    def get_specialized_version(self) -> str:
        return f"{self.version}_{self.subject_id}"

class ControlFlowGraphFactory:
    """
    Factory class for creating Control Flow Graph instances from FHIR PlanDefinition resources.
    """

    @staticmethod
    def validate_fhir_plandefinition(plan_definition: PlanDefinition, throw_exception: bool = True) -> bool:
        """
        Validates if the FHIR PlanDefinition resource is valid for conversion to a Control Flow Graph.
        
        :param plan_definition: The FHIR PlanDefinition resource to validate.
        :type plan_definition: PlanDefinition
        :param throw_exception: Whether to throw an exception if the PlanDefinition is invalid.
        :type throw_exception: bool
        
        :returns: True if the PlanDefinition is valid, False otherwise.
        :rtype: bool
        """
        is_valid = True

        if not plan_definition.id:
            if throw_exception:
                raise PlanDefinitionValidationException("PlanDefinition must have an id.")
            is_valid = False
        if not plan_definition.name:
            if throw_exception:
                raise PlanDefinitionValidationException("PlanDefinition must have a name.")
            is_valid = False
        if not plan_definition.title:
            if throw_exception:
                raise PlanDefinitionValidationException("PlanDefinition must have a title.")
            is_valid = False
        if not plan_definition.description:
            if throw_exception:
                raise PlanDefinitionValidationException("PlanDefinition must have a description.")
            is_valid = False
        if not plan_definition.version:
            if throw_exception:
                raise PlanDefinitionValidationException("PlanDefinition must have a version.")
            is_valid = False

        if not plan_definition.action or len(plan_definition.action) == 0:
            if throw_exception:
                raise PlanDefinitionValidationException("PlanDefinition must have at least one action.")
            is_valid = False

        actions_valid = ControlFlowGraphFactory._validate_fhir_actions(
            plan_definition.action or [], throw_exception, PlanDefinitionValidationException
        )
        is_valid = is_valid and actions_valid
        return is_valid

    @staticmethod
    def _validate_fhir_actions(
        actions: List[Union[PlanDefinitionAction, RequestOrchestrationAction]],
        throw_exception: bool,
        exception_type: Type[Exception],
    ) -> bool:
        """
        Apply the same action validation rules to both FHIR workflow resources.

        Nested actions are checked recursively using the same rules.

        :param actions: Actions to validate.
        :type actions: List[Union[PlanDefinitionAction, RequestOrchestrationAction]]
        :param throw_exception: Whether to raise on the first invalid action.
        :type throw_exception: bool
        :param exception_type: Validation exception associated with the source resource.
        :type exception_type: Type[Exception]
        :return: Whether all actions satisfy the shared validation rules.
        :rtype: bool
        """
        is_valid = True
        for action in actions:
            if not action.linkId:
                if throw_exception:
                    raise exception_type("Action must have a linkId.")
                is_valid = False
            if not action.title:
                if throw_exception:
                    raise exception_type("Action must have a title.")
                is_valid = False
            if not action.definitionCanonical:
                if throw_exception:
                    raise exception_type("Action must have a definitionCanonical.")
                is_valid = False
            if action.timingTiming:
                if not FHIRTemporalConstraint.validate_fhir_timing(action.timingTiming, False):
                    if throw_exception:
                        raise exception_type(f"Action {action.linkId} has an invalid timing.")
                    is_valid = False
            if action.condition and len(action.condition) > 0:
                if not action.condition[0].expression or not action.condition[0].expression.expression or not action.condition[0].expression.description:
                    if throw_exception:
                        raise exception_type(f"Action {action.linkId} has an invalid condition.")
                    is_valid = False
            
            if action.relatedAction or []:
                for related_action in action.relatedAction or []:
                    if not related_action.relationship:
                        if throw_exception:
                            raise exception_type(f"RelatedAction in action {action.linkId} must have a relationship.")
                        is_valid = False
                    if not related_action.targetId:
                        if throw_exception:
                            raise exception_type(f"RelatedAction in action {action.linkId} must have a targetId.")
                        is_valid = False
                    if related_action.relationship not in [r.value for r in FHIRRelationshipType]:
                        if throw_exception:
                            raise exception_type(f"RelatedAction in action {action.linkId} must have a valid relationship.")
                        is_valid = False
                    if related_action.offsetDuration:
                        if not FHIRTemporalConstraint.validate_fhir_duration_offset(related_action.offsetDuration, False):
                            if throw_exception:
                                raise exception_type(f"RelatedAction in action {action.linkId} offsetDuration is invalid.")

                            is_valid = False
            
            for dv in action.dynamicValue or []:
                if not dv.path:
                    if throw_exception:
                        raise exception_type(f"DynamicValue in action {action.linkId} must have a path.")
                    is_valid = False
                if not dv.expression:
                    if throw_exception:
                        raise exception_type(f"DynamicValue in action {action.linkId} must have an expression.")
                    is_valid = False
                else:
                    if not dv.expression.expression:
                        if throw_exception:
                            raise exception_type(f"DynamicValue in action {action.linkId} expression must have an expression.")
                        is_valid = False
            if action.action:
                if not ControlFlowGraphFactory._validate_fhir_actions(
                    action.action, throw_exception, exception_type
                ):
                    is_valid = False
        return is_valid

    @classmethod
    def from_plandefinition(cls, plan_definition: PlanDefinition) -> ControlFlowGraph:
        """
        Method to create a Control Flow Graph from a PlanDefinition.

        :param plan_definition: PlanDefinition to convert to Control Flow Graph.
        :type plan_definition: PlanDefinition
        :return: Control Flow Graph.
        :rtype: ControlFlowGraph
        """
        cls.validate_fhir_plandefinition(plan_definition)

        cfg = ControlFlowGraph(
            cfg_type=CFGType.CLASSIC,
            id=plan_definition.id,
            version=plan_definition.version,
            title=plan_definition.title,
            name=plan_definition.name,
            description=plan_definition.description,
        )

        action_conditions = {}

        for action in plan_definition.action or []:
            if action.condition:
                action_conditions[action.linkId] = FHIRExecutionCondition(
                    # pyrefly: ignore [missing-attribute, unsupported-operation]
                    expression=action.condition[0].expression.expression,
                    # pyrefly: ignore [missing-attribute, unsupported-operation]
                    description=action.condition[0].expression.description
                )
            
            attrs = {}
            for dv in action.dynamicValue or []:
                # pyrefly: ignore [missing-attribute, unsupported-operation]
                attrs[dv.path] = dv.expression.expression
            
            node_timing = None
            if action.timingTiming:
                node_timing = FHIRTemporalConstraint.from_fhir_timing(action.timingTiming)
            
            if any([r.offsetDuration for r in action.relatedAction or []]):
                if node_timing:
                    # pyrefly: ignore [unsupported-operation]
                    node_timing.add_offset_duration(action.relatedAction[0].offsetDuration)
                else:
                    # pyrefly: ignore [unsupported-operation]
                    node_timing = FHIRTemporalConstraint.from_fhir_offset_duration(action.relatedAction[0].offsetDuration)

            cfg.add_node(ActionNode(
                id=action.linkId,
                title=action.title,
                # pyrefly: ignore [missing-attribute, unsupported-operation]
                activity_definition=action_definition_id(action.definitionCanonical),
                fhir_temporal_constraint=node_timing,
                attributes=attrs,
            ))

        
        for action in plan_definition.action or []:
            for rel_act in action.relatedAction or []:
                cfg.add_edge(
                    src=rel_act.targetId,
                    tgt=action.linkId,
                    # pyrefly: ignore [missing-attribute]
                    relationship=FHIRRelationshipType(rel_act.relationship),
                    execution_condition=action_conditions.get(action.linkId),
                )

        # 4. Create start node and edges (actions without relatedAction)
        start_node = EventNode(
            id="start_node",
            event_type=CFGEventType.START
        )
        cfg.add_node(node=start_node, start=True)
        
        starting_nodes = [
            node for node in cfg.nodes.values() if len(node.incoming) == 0
        ]
        
        for node in starting_nodes:
            if node.id != "start_node":
                cfg.add_edge(
                    src=start_node.id,
                    tgt=node.id,
                    relationship=FHIRRelationshipType.AFTER_END,
                    execution_condition=action_conditions.get(node.id)
                )

        # 5. Create end node and edges (nodes without outgoing edges)
        end_node = EventNode(
            id="end_node",
            event_type=CFGEventType.END
        )
        cfg.add_node(node=end_node, end=True)
        ending_nodes = [n for n in cfg.nodes.values() if len(n.outgoing) == 0]
        
        for node in ending_nodes:
            if node.id != "end_node":
                cfg.add_edge(
                    src=node.id,
                    tgt=end_node.id,
                    relationship=FHIRRelationshipType.AFTER_END,
                )

        i = 1
        n_to_fake = []
        for node in cfg.nodes.values():
            if any([e.execution_condition is not None for e in node.incoming]):
                src_node = node.incoming[0].source
                if len(src_node.outgoing) == 1:
                    n_to_fake.append(node)

        for n in n_to_fake:
            for ie in n.incoming:
                src_node = ie.source
                cfg.add_node(FakeNode(
                    id=f"F{i}"
                ))
                cfg.add_edge(src=src_node.id, tgt=f"F{i}", relationship=FHIRRelationshipType.AFTER_END, execution_condition=FHIRExecutionCondition(expression="Otherwise", description="Otherwise"))
                cfg.add_edge(src=f"F{i}", tgt="end_node", relationship=FHIRRelationshipType.AFTER_END, execution_condition=FHIRExecutionCondition(expression="Otherwise", description="Otherwise"))
            i += 1
        
        return cfg

    @classmethod
    def validate_fhir_request_orchestration(
        cls,
        request_orchestration: RequestOrchestration,
        plan_cfg: ControlFlowGraph,
        throw_exception: bool = True,
    ) -> bool:
        """
        Validate absolute versioned plan URLs, instance references and action identities.

        Added and removed actions are allowed. Actions sharing a linkId with
        the source CFG must reference the same ActivityDefinition logical ID.

        :param request_orchestration: Patient-specific workflow to validate.
        :type request_orchestration: RequestOrchestration
        :param plan_cfg: Source PlanDefinition CFG used to compare action identities.
        :type plan_cfg: ControlFlowGraph
        :param throw_exception: Whether to raise on the first validation failure.
        :type throw_exception: bool
        :return: Whether the RequestOrchestration satisfies the validation rules.
        :rtype: bool
        :raises RequestOrchestrationValidationException: If validation fails and throwing is enabled.
        """
        def invalid(message: str) -> bool:
            """
            Report a resource validation failure.

            :param message: Description of the validation failure.
            :type message: str
            :return: False when exception throwing is disabled.
            :rtype: bool
            """
            if throw_exception:
                raise RequestOrchestrationValidationException(message)
            return False

        subject = request_orchestration.subject
        reference = subject.reference if subject is not None else None
        if not reference or re.fullmatch(
            r"(?:https?://[^\s?#]+/)?Patient/[A-Za-z0-9.-]{1,64}", reference
        ) is None:
            return invalid("RequestOrchestration.subject.reference must identify a Patient resource.")

        canonicals = request_orchestration.instantiatesCanonical or []
        canonical_error = (
            "RequestOrchestration.instantiatesCanonical must contain exactly one "
            "absolute HTTP(S) URL in the format "
            "https://<host>[/<base-path>]/PlanDefinition/<id>|<version>."
        )
        if len(canonicals) != 1:
            return invalid(canonical_error)
        canonical = canonicals[0]
        if not isinstance(canonical, str) or re.search(r"\s", canonical):
            return invalid(canonical_error)
        reference, separator, version = canonical.partition("|")
        if not separator or re.fullmatch(r"[^\s|/#?]+", version) is None:
            return invalid(canonical_error)
        try:
            parsed = urlsplit(reference)
            # Accessing port also rejects malformed and out-of-range ports.
            parsed.port
            valid_url = (
                parsed.scheme in {"http", "https"}
                and bool(parsed.hostname)
                and not parsed.query
                and not parsed.fragment
                and re.fullmatch(
                    r"/(?:[^/\s?#|]+/)*PlanDefinition/[A-Za-z0-9.-]{1,64}",
                    parsed.path,
                ) is not None
            )
        except ValueError:
            valid_url = False
        if not valid_url:
            return invalid(canonical_error)

        if not request_orchestration.action:
            return invalid("RequestOrchestration must have at least one action.")
        if not cls._validate_fhir_actions(
            request_orchestration.action, throw_exception, RequestOrchestrationValidationException
        ):
            return False

        plan_actions = {
            node.id: node.activity_definition
            for node in plan_cfg.nodes.values()
            if isinstance(node, ActionNode)
        }
        pending = list(request_orchestration.action)
        while pending:
            action = pending.pop(0)
            pending[0:0] = list(action.action or [])
            if action.resource is None or not action.resource.reference or not action.resource.reference.strip():
                return invalid(f"Action {action.linkId} must have a populated resource.reference.")
            try:
                definition_id = action_definition_id(action.definitionCanonical)
            except ContractIdException as error:
                return invalid(f"Action {action.linkId} has an invalid ActivityDefinition reference: {error}")
            if action.linkId in plan_actions and plan_actions[action.linkId] != definition_id:
                return invalid(
                    f"Action {action.linkId} must reference ActivityDefinition/"
                    f"{plan_actions[action.linkId]}, as in the source PlanDefinition CFG."
                )
        return True

    @classmethod
    def from_request_orchestration(cls, request_orchestration: RequestOrchestration, plan_cfg: ControlFlowGraph) -> InstanceControlFlowGraph:
        """
        Method to create a Control Flow Graph from a RequestOrchestration.

        :param request_orchestration: RequestOrchestration to convert to Control Flow Graph.
        :type request_orchestration: RequestOrchestration
        :param plan_cfg: Control Flow Graph of the PlanDefinition that is definition for the RequestOrchestration.
        :type plan_cfg: ControlFlowGraph
        :return: Control Flow Graph.
        :rtype: ControlFlowGraph
        """
        cls.validate_fhir_request_orchestration(request_orchestration, plan_cfg)

        cfg = InstanceControlFlowGraph(
            cfg_type=CFGType.CLASSIC,
            id=plan_cfg.id,
            version=plan_cfg.version,
            title=plan_cfg.title,
            name=plan_cfg.name,
            description=plan_cfg.description,
            request_orchestration_id=request_orchestration.id,
            subject_id=request_orchestration.subject.reference.split("/")[-1]
        )

        action_conditions = {}

        for action in request_orchestration.action or []:
            if action.condition:
                action_conditions[action.linkId] = FHIRExecutionCondition(
                    # pyrefly: ignore [missing-attribute, unsupported-operation]
                    expression=action.condition[0].expression.expression,
                    # pyrefly: ignore [missing-attribute, unsupported-operation]
                    description=action.condition[0].expression.description
                )
            
            attrs = {}
            for dv in action.dynamicValue or []:
                # pyrefly: ignore [missing-attribute, unsupported-operation]
                attrs[dv.path] = dv.expression.expression
            
            node_timing = None
            if action.timingTiming:
                node_timing = FHIRTemporalConstraint.from_fhir_timing(action.timingTiming)
            
            if any([r.offsetDuration for r in action.relatedAction or []]):
                if node_timing:
                    # pyrefly: ignore [unsupported-operation]
                    node_timing.add_offset_duration(action.relatedAction[0].offsetDuration)
                else:
                    # pyrefly: ignore [unsupported-operation]
                    node_timing = FHIRTemporalConstraint.from_fhir_offset_duration(action.relatedAction[0].offsetDuration)

            cfg.add_node(ActionNode(
                id=action.linkId,
                title=action.title,
                # pyrefly: ignore [missing-attribute, unsupported-operation]
                activity_definition=action_definition_id(action.definitionCanonical),
                fhir_temporal_constraint=node_timing,
                attributes=attrs,
            ))

        
        for action in request_orchestration.action or []:
            for rel_act in action.relatedAction or []:
                cfg.add_edge(
                    src=rel_act.targetId,
                    tgt=action.linkId,
                    # pyrefly: ignore [missing-attribute]
                    relationship=FHIRRelationshipType(rel_act.relationship),
                    execution_condition=action_conditions.get(action.linkId),
                )

        # 4. Create start node and edges (actions without relatedAction)
        start_node = EventNode(
            id="start_node",
            event_type=CFGEventType.START
        )
        cfg.add_node(node=start_node, start=True)
        
        starting_nodes = [
            node for node in cfg.nodes.values() if len(node.incoming) == 0
        ]
        
        for node in starting_nodes:
            if node.id != "start_node":
                cfg.add_edge(
                    src=start_node.id,
                    tgt=node.id,
                    relationship=FHIRRelationshipType.AFTER_END,
                    execution_condition=action_conditions.get(node.id)
                )

        # 5. Create end node and edges (nodes without outgoing edges)
        end_node = EventNode(
            id="end_node",
            event_type=CFGEventType.END
        )
        cfg.add_node(node=end_node, end=True)
        ending_nodes = [n for n in cfg.nodes.values() if len(n.outgoing) == 0]
        
        for node in ending_nodes:
            if node.id != "end_node":
                cfg.add_edge(
                    src=node.id,
                    tgt=end_node.id,
                    relationship=FHIRRelationshipType.AFTER_END,
                )

        i = 1
        n_to_fake = []
        for node in cfg.nodes.values():
            if any([e.execution_condition is not None for e in node.incoming]):
                src_node = node.incoming[0].source
                if len(src_node.outgoing) == 1:
                    n_to_fake.append(node)

        for n in n_to_fake:
            for ie in n.incoming:
                src_node = ie.source
                cfg.add_node(FakeNode(
                    id=f"F{i}"
                ))
                cfg.add_edge(src=src_node.id, tgt=f"F{i}", relationship=FHIRRelationshipType.AFTER_END, execution_condition=FHIRExecutionCondition(expression="Otherwise", description="Otherwise"))
                cfg.add_edge(src=f"F{i}", tgt="end_node", relationship=FHIRRelationshipType.AFTER_END, execution_condition=FHIRExecutionCondition(expression="Otherwise", description="Otherwise"))
            i += 1
        
        return cfg
    
    @staticmethod
    def cfg_with_gateways(
        control_flow_graph: ControlFlowGraph,
    ) -> ControlFlowGraph:
        """
        Insert divergent/convergent gateways by evaluating nested regions.

        Regions are processed from the innermost to the outermost.
        A candidate region may share its exit node with other regions:
        external incoming edges at the exit are allowed, while external
        entries into internal nodes and external exits from internal nodes
        are rejected.

        Gateway classification:
        - EXCLUSIVE if at least one outgoing edge is conditional.
        - PARALLEL otherwise.

        Assumptions:
        - The CFG has one start node and one end node.
        - Every reachable node can reach the end node.
        - Unconditional branching represents parallel execution.
        """
        import copy

        cfg = copy.deepcopy(control_flow_graph)

        if cfg.start_node is None or cfg.end_node is None:
            raise ValueError("CFG must have a start node and an end node.")

        if not cfg.nodes:
            raise ValueError("Cannot transform an empty CFG.")

        start_id = cfg.start_node.id
        end_id = cfg.end_node.id

        # Factor repeated conditional frontiers among children of a parallel
        # split. Other parallel branches may continue independently (P09).
        normalized_hubs = []

        def frontier_signature(es):
            return tuple(sorted(
                (e.target.id, e.relationship.value,
                 e.execution_condition.expression if e.execution_condition else None,
                 e.execution_condition.description if e.execution_condition else None)
                for e in es
            ))

        for root in list(cfg.nodes.values()):
            root_edges = list(root.outgoing)
            if len(root_edges) < 2 or any(
                e.execution_condition is not None for e in root_edges
            ):
                continue
            children = [e.target for e in root_edges]
            if len({n.id for n in children}) != len(children):
                continue
            groups = {}
            for node in children:
                es = list(node.outgoing)
                if len(node.incoming) != 1 or len(es) < 2:
                    continue
                if any(e.execution_condition is None for e in es):
                    continue
                if len({e.target.id for e in es}) != len(es):
                    continue
                groups.setdefault(frontier_signature(es), []).append(node)

            for cohort in groups.values():
                if len(cohort) < 2:
                    continue
                frontiers = [list(n.outgoing) for n in cohort]
                first = frontiers[0]
                cohort_ids = {n.id for n in cohort}
                targets = {e.target.id for e in first}
                if targets & (cohort_ids | {root.id}):
                    continue
                if any({e.source.id for e in cfg.nodes[t].incoming} != cohort_ids
                       for t in targets):
                    continue
                if any(e.relationship != FHIRRelationshipType.AFTER_END
                       for es in frontiers for e in es):
                    raise ValueError("Repeated conditional frontier requires after-end edges")
                i = 1
                while f"synchronized_choice_{i}" in cfg.nodes:
                    i += 1
                hub_id = f"synchronized_choice_{i}"
                join_id = f"{hub_id}_join"
                while join_id in cfg.nodes:
                    join_id += "_"
                cfg.add_node(GatewayNode(
                    join_id, CFGGatewayClass.PARALLEL,
                    CFGGatewayDirection.CONVERGENT))
                cfg.add_node(FakeNode(hub_id))
                normalized_hubs.append(hub_id)
                for es in frontiers:
                    for edge in es:
                        cfg.remove_edge(edge.id)
                for node in cohort:
                    cfg.add_edge(node.id, join_id, FHIRRelationshipType.AFTER_END)
                cfg.add_edge(join_id, hub_id, FHIRRelationshipType.AFTER_END)
                for edge in first:
                    cfg.add_edge(hub_id, edge.target.id, edge.relationship,
                                 edge.execution_condition)

        # ---------------------------------------------------------
        # Graph navigation
        # ---------------------------------------------------------

        def successors(node_id: str) -> set[str]:
            return {
                edge.target.id
                for edge in cfg.nodes[node_id].outgoing
            }

        def predecessors(node_id: str) -> set[str]:
            return {
                edge.source.id
                for edge in cfg.nodes[node_id].incoming
            }

        def reachable_from(start: str) -> set[str]:
            visited = set()
            stack = [start]

            while stack:
                current = stack.pop()

                if current in visited:
                    continue

                visited.add(current)
                stack.extend(successors(current) - visited)

            return visited

        def can_reach_end() -> set[str]:
            visited = set()
            stack = [end_id]

            while stack:
                current = stack.pop()

                if current in visited:
                    continue

                visited.add(current)
                stack.extend(predecessors(current) - visited)

            return visited

        # ---------------------------------------------------------
        # Dominators and post-dominators
        # ---------------------------------------------------------

        def compute_dominators() -> dict[str, set[str]]:
            reachable = reachable_from(start_id)

            dom = {
                node_id: (
                    {node_id}
                    if node_id == start_id
                    else set(reachable)
                )
                for node_id in reachable
            }

            changed = True

            while changed:
                changed = False

                for node_id in reachable - {start_id}:
                    preds = predecessors(node_id) & reachable

                    if not preds:
                        new_dom = {node_id}
                    else:
                        common = set(reachable)

                        for pred_id in preds:
                            common &= dom[pred_id]

                        new_dom = common | {node_id}

                    if new_dom != dom[node_id]:
                        dom[node_id] = new_dom
                        changed = True

            return dom

        def compute_postdominators() -> dict[str, set[str]]:
            reachable = reachable_from(start_id)
            can_finish = can_reach_end()

            invalid = reachable - can_finish

            if invalid:
                raise ValueError(
                    "Some reachable nodes cannot reach the CFG exit: "
                    f"{sorted(invalid)}"
                )

            pdom = {
                node_id: (
                    {node_id}
                    if node_id == end_id
                    else set(reachable)
                )
                for node_id in reachable
            }

            changed = True

            while changed:
                changed = False

                for node_id in reachable - {end_id}:
                    succs = successors(node_id) & reachable

                    if not succs:
                        raise ValueError(
                            f"Node {node_id!r} has no path to the CFG exit."
                        )

                    common = set(reachable)

                    for succ_id in succs:
                        common &= pdom[succ_id]

                    new_pdom = common | {node_id}

                    if new_pdom != pdom[node_id]:
                        pdom[node_id] = new_pdom
                        changed = True

            return pdom

        def immediate_postdominator(
            node_id: str,
            pdom: dict[str, set[str]],
        ) -> str | None:
            candidates = pdom.get(node_id, set()) - {node_id}

            immediate = [
                candidate
                for candidate in candidates
                if all(
                    other in pdom[candidate]
                    for other in candidates
                    if other != candidate
                )
            ]

            return immediate[0] if len(immediate) == 1 else None

        # ---------------------------------------------------------
        # Candidate region construction
        # ---------------------------------------------------------

        def build_region(
            split_id: str,
            join_id: str,
            dom: dict[str, set[str]],
            pdom: dict[str, set[str]],
        ) -> set[str]:
            """
            Build a candidate region using dominance and post-dominance.

            IMPORTANT:
            Do not require split_id to dominate join_id.
            A shared exit may also be reachable through an external branch.
            """

            if split_id == join_id:
                raise ValueError(
                    "A split and its join must be different nodes."
                )

            if join_id not in pdom.get(split_id, set()):
                raise ValueError(
                    f"Node {join_id!r} does not post-dominate "
                    f"split {split_id!r}."
                )

            # The body includes nodes dominated by the split and
            # post-dominated by the candidate join.
            body = {
                node_id
                for node_id in cfg.nodes
                if node_id not in {split_id, join_id}
                and split_id in dom.get(node_id, set())
                and join_id in pdom.get(node_id, set())
            }

            region = body | {split_id, join_id}

            # Every branch leaving the split must remain in the region
            # until it reaches the candidate join.
            for edge in cfg.nodes[split_id].outgoing:
                first = edge.target.id

                if first == join_id:
                    continue

                visited = set()
                stack = [first]

                while stack:
                    current = stack.pop()

                    if current == join_id or current in visited:
                        continue

                    if current not in region:
                        raise ValueError(
                            f"Branch from {split_id!r} escapes candidate "
                            f"region before reaching {join_id!r}: {current!r}."
                        )

                    visited.add(current)
                    stack.extend(successors(current) - visited)

            # No external edge may enter the interior of the region.
            # External incoming edges at the join are explicitly allowed.
            for node_id in body:
                for edge in cfg.nodes[node_id].incoming:
                    if edge.source.id not in region:
                        raise ValueError(
                            f"Candidate region {split_id!r}->{join_id!r} "
                            f"has an external entry at internal node "
                            f"{node_id!r}."
                        )

            # No internal node may leave the region except through the join.
            for node_id in body | {split_id}:
                for edge in cfg.nodes[node_id].outgoing:
                    if edge.target.id not in region:
                        raise ValueError(
                            f"Candidate region {split_id!r}->{join_id!r} "
                            f"has an external exit from {node_id!r}."
                        )

            return region

        # ---------------------------------------------------------
        # Gateway insertion helpers
        # ---------------------------------------------------------

        gateway_counter = 1

        def next_gateway_id(direction: str) -> str:
            nonlocal gateway_counter

            while True:
                gateway_id = f"{direction}_gat_{gateway_counter}"
                gateway_counter += 1

                if gateway_id not in cfg.nodes:
                    return gateway_id

        def add_edge(
            src: str,
            tgt: str,
            relationship: FHIRRelationshipType,
            execution_condition: Optional[FHIRExecutionCondition] = None,
        ) -> None:
            cfg.add_edge(
                src=src,
                tgt=tgt,
                relationship=relationship,
                execution_condition=execution_condition,
            )

        def infer_gateway_class(
            outgoing_edges: list[CFGEdge],
        ) -> CFGGatewayClass:
            if any(
                edge.execution_condition is not None
                for edge in outgoing_edges
            ):
                return CFGGatewayClass.EXCLUSIVE

            return CFGGatewayClass.PARALLEL

        def insert_gateway_pair(
            split_id: str,
            join_id: str,
            gateway_class: CFGGatewayClass,
            region: set[str],
        ) -> None:
            split_node = cfg.nodes[split_id]
            original_outgoing = list(split_node.outgoing)

            if len(original_outgoing) < 2:
                return

            div_id = next_gateway_id("div")
            existing_join = cfg.nodes[join_id]
            reuse_join = (isinstance(existing_join, GatewayNode)
                          and existing_join.gateway_direction == CFGGatewayDirection.CONVERGENT
                          and existing_join.gateway_class == gateway_class
                          and all(e.source.id in region for e in existing_join.incoming))
            conv_id = join_id if reuse_join else next_gateway_id("conv")

            div_node = GatewayNode(
                id=div_id,
                gateway_class=gateway_class,
                gateway_direction=CFGGatewayDirection.DIVERGENT,
            )

            conv_node = GatewayNode(
                id=conv_id,
                gateway_class=gateway_class,
                gateway_direction=CFGGatewayDirection.CONVERGENT,
            )

            cfg.add_node(div_node)
            if not reuse_join:
                cfg.add_node(conv_node)

            # Redirect split -> branches through the divergent gateway.
            for edge in original_outgoing:
                cfg.remove_edge(edge.id)

            add_edge(
                src=split_id,
                tgt=div_id,
                relationship=FHIRRelationshipType.AFTER_END,
            )

            for edge in original_outgoing:
                add_edge(
                    src=div_id,
                    tgt=edge.target.id,
                    relationship=edge.relationship,
                    execution_condition=edge.execution_condition,
                )

            # Redirect only incoming edges to the join that originate
            # within this region. External incoming edges must remain.
            join_node = cfg.nodes[join_id]
            incoming_to_join = [] if reuse_join else list(join_node.incoming)

            for edge in incoming_to_join:
                source_id = edge.source.id

                if source_id not in region and source_id != div_id:
                    continue

                # The split itself is not normally an incoming source
                # to the join, but preserve safety if it is.
                if source_id == join_id:
                    continue

                relationship = edge.relationship
                condition = edge.execution_condition

                cfg.remove_edge(edge.id)

                add_edge(
                    src=source_id,
                    tgt=conv_id,
                    relationship=relationship,
                    execution_condition=condition,
                )

            if not reuse_join:
                add_edge(
                    src=conv_id,
                    tgt=join_id,
                    relationship=FHIRRelationshipType.AFTER_END,
                )

        # ---------------------------------------------------------
        # Discover regions in the ORIGINAL graph
        # ---------------------------------------------------------

        dom = compute_dominators()
        pdom = compute_postdominators()

        candidates: list[tuple[int, str, str, set[str]]] = []

        original_split_ids = [
            node.id
            for node in cfg.nodes.values()
            if len(node.outgoing) > 1 and not isinstance(node, GatewayNode)
        ]

        for split_id in original_split_ids:
            join_id = immediate_postdominator(split_id, pdom)

            if join_id is None:
                raise ValueError(
                    f"Could not identify a unique immediate post-dominator "
                    f"for branching node {split_id!r}."
                )

            region = build_region(split_id, join_id, dom, pdom)

            candidates.append(
                (len(region), split_id, join_id, region)
            )

        # Innermost regions first. The original candidate regions are
        # retained so that nested structure can be evaluated consistently.
        candidates.sort(key=lambda item: item[0])

        # ---------------------------------------------------------
        # Transform regions from inner to outer
        # ---------------------------------------------------------

        for _, split_id, original_join_id, _ in candidates:
            if split_id not in cfg.nodes:
                continue

            if len(cfg.nodes[split_id].outgoing) < 2:
                continue

            # Recompute graph properties after each transformation.
            dom = compute_dominators()
            pdom = compute_postdominators()

            join_id = immediate_postdominator(split_id, pdom)

            if join_id is None:
                # The split may have been affected by an inner rewrite.
                # Do not silently choose an arbitrary join.
                raise ValueError(
                    f"Could not identify a unique join for split "
                    f"{split_id!r} after transforming inner regions."
                )

            region = build_region(split_id, join_id, dom, pdom)

            outgoing_edges = list(cfg.nodes[split_id].outgoing)
            gateway_class = infer_gateway_class(outgoing_edges)

            insert_gateway_pair(
                split_id=split_id,
                join_id=join_id,
                gateway_class=gateway_class,
                region=region,
            )

        # The synthetic hub now lies between the AND join and XOR split.
        # Remove only hubs introduced here; original FakeNodes remain intact.
        for hub_id in normalized_hubs:
            hub = cfg.nodes[hub_id]
            if len(hub.incoming) != 1 or len(hub.outgoing) != 1:
                raise ValueError("Synchronized choice was not fully structured")
            before, after = hub.incoming[0], hub.outgoing[0]
            if before.execution_condition is not None or after.execution_condition is not None:
                raise ValueError("Unexpected condition on synchronization connector")
            cfg.remove_edge(before.id)
            cfg.remove_edge(after.id)
            cfg.nodes.pop(hub_id)
            cfg.add_edge(before.source.id, after.target.id,
                         FHIRRelationshipType.AFTER_END)
        cfg.cfg_type = CFGType.GATEWAY
        return cfg
    
    @staticmethod
    def _cycle_signature(action):
        """
        Build a label-independent signature for grouping equal scheduled actions.

        :param action: Scheduled action whose temporal metadata is compared.
        :type action: ActionNode
        :return: Comparable schedule signature.
        :rtype: str
        """
        import json
        payload = action.fhir_temporal_constraint.to_json()
        payload.pop("label", None)
        for field in ("day_of_week", "time_of_day", "when"):
            payload[field] = sorted(payload[field] or [])
        return json.dumps(payload, sort_keys=True)


    @classmethod
    def _process_cycle_action_ids(cls, cfg):
        """Identify exactly the cycle eligible to replace the process start.

        A single unguarded entry can schedule an action, or a complete parallel
        group with identical constraints. Other independently scheduled initial
        branches remain local cycles and cannot contain further cycles.
        """
        start = cfg.start_node
        if start is None or len(start.outgoing) != 1:
            return set()
        edge = start.outgoing[0]
        if edge.execution_condition is not None:
            return set()
        entry = edge.target
        def is_cycle(node):
            return (isinstance(node, ActionNode)
                    and node.fhir_temporal_constraint is not None
                    and any(c in node.fhir_temporal_constraint.get_categories()
                            for c in (TemporalCategory.STANDARD_CYCLE, TemporalCategory.INSTANCE_CYCLE, TemporalCategory.KEEP_ALIVE_BOUND)))
        if is_cycle(entry) and len(entry.incoming) == 1:
            return {entry.id}
        if not (isinstance(entry, GatewayNode)
                and entry.gateway_class == CFGGatewayClass.PARALLEL
                and entry.gateway_direction == CFGGatewayDirection.DIVERGENT
                and len(entry.incoming) == 1 and entry.outgoing):
            return set()
        members = [e.target for e in entry.outgoing]
        if any(e.execution_condition is not None for e in entry.outgoing):
            return set()
        if not all(is_cycle(n) and len(n.incoming) == 1 for n in members):
            return set()
        if len({cls._cycle_signature(n) for n in members}) != 1:
            return set()
        return {n.id for n in members}


    @classmethod
    def validate_temporal_structures(cls, control_flow_graph : ControlFlowGraph, throw_exception: bool = True)  -> bool:
        """
        Check temporal constraints in the CFG.

        :param control_flow_graph: The Control Flow Graph to validate.
        :type control_flow_graph: ControlFlowGraph
        :param throw_exception: Whether to throw an exception if the CFG is invalid.
        :type throw_exception: bool
        :return: True if the CFG is valid, False otherwise.
        :rtype: bool
        """
        process_cycle_ids = cls._process_cycle_action_ids(control_flow_graph)
        nodes_with_tc = {}
        for node_id, node in control_flow_graph.nodes.items():
            if node.node_type == CFGNodeType.ACTION:
                node : ActionNode = node
                if node.fhir_temporal_constraint:
                    nodes_with_tc[node_id] = node

        if len(nodes_with_tc) == 0:
            return True
        
        is_valid = True

        for node in nodes_with_tc.values():
            # pyrefly: ignore [missing-attribute]
            tc_categories = node.fhir_temporal_constraint.get_categories()
            if any(c in tc_categories for c in (TemporalCategory.INSTANCE_CYCLE, TemporalCategory.STANDARD_CYCLE, TemporalCategory.KEEP_ALIVE_BOUND)):
                bound_paths = control_flow_graph.find_all_bound_paths(node)
                # pyrefly: ignore [missing-attribute]
                cycle_iteration_duration = node.fhir_temporal_constraint.get_cycle_iteration_duration_in_seconds()
                for path in bound_paths:
                    path_duration = 0 # in seconds
                    for node_id in path[1:]:
                        pnode : ActionNode = control_flow_graph.nodes[node_id]
                        if pnode.node_type != CFGNodeType.ACTION:
                            continue
                        elif not pnode.fhir_temporal_constraint:
                            continue
                        else:
                            pnode_categories = pnode.fhir_temporal_constraint.get_categories()
                            if any(c in pnode_categories for c in (TemporalCategory.INSTANCE_CYCLE, TemporalCategory.STANDARD_CYCLE, TemporalCategory.KEEP_ALIVE_BOUND)):
                                # Only the process-level scheduler can enclose local cycles.
                                # Each local scheduler is still validated on its own paths,
                                # so a third scheduling level remains prohibited.
                                if node.id in process_cycle_ids:
                                    continue
                                is_valid = False
                                if throw_exception:
                                    raise ValueError(f"Cycle temporal constraint for {node_id} node is inside the bound area of node {node.id}")
                                return False
                            elif TemporalCategory.EXECUTION_DURATION in pnode_categories:
                                if pnode.fhir_temporal_constraint.duration_max is not None:
                                    # pyrefly: ignore [unsupported-operation]
                                    path_duration += pnode.fhir_temporal_constraint.get_execution_bound_in_seconds()
                                else:
                                    # pyrefly: ignore [unsupported-operation]
                                    path_duration += pnode.fhir_temporal_constraint.get_execution_duration_in_seconds()
                    if cycle_iteration_duration is not None and cycle_iteration_duration < path_duration:
                        is_valid = False
                        if throw_exception:
                            raise ValueError(f"Cycle temporal constraint for {node.id} node is too short. Cycle iteration duration: {cycle_iteration_duration}, Path duration: {path_duration}")
                        return False

        return is_valid


    @classmethod
    def cfg_with_temporal_structures(cls, control_flow_graph: ControlFlowGraph) -> ControlFlowGraph:
        """Build timer-started cycles at process or subprocess scope.

        Equal constraints on direct children of a parallel split share a cycle.
        Keep Alive is an independent start/timer/end lane in the same scope.
        A lifetime without a recurrence also creates a scheduler with unset values.
        The input graph is copied; a temporal CFG is returned unchanged as a copy.

        :param control_flow_graph: Classic or gateway CFG to enrich.
        :type control_flow_graph: ControlFlowGraph
        :return: Temporal CFG retaining combined action declarations and schedule metadata.
        :rtype: ControlFlowGraph
        :raises ValueError: If cycle nesting or combined activation semantics are unsupported.
        """
        import copy
        import json

        cfg = copy.deepcopy(control_flow_graph)
        if cfg.cfg_type == CFGType.TEMPORAL:
            return cfg
        if cfg.cfg_type == CFGType.CLASSIC:
            cfg = cls.cfg_with_gateways(cfg)
        cls.validate_temporal_structures(cfg)
        if cfg.start_node is None or cfg.end_node is None:
            raise ValueError("Temporal CFG requires start and end nodes")

        reserved = set(cfg.nodes)

        def fresh(prefix):
            i = 1
            while f"{prefix}_{i}" in reserved:
                i += 1
            result = f"{prefix}_{i}"
            reserved.add(result)
            return result

        def add(scope, source, target, relationship=FHIRRelationshipType.AFTER_END, condition=None):
            if isinstance(scope, BlockNode):
                scope.add_edge(CFGEdge(scope.nodes[source], scope.nodes[target],
                                       relationship, condition), update_nodes=True)
            else:
                scope.add_edge(source, target, relationship, condition)

        def keep_alive(scope, action):
            tc = action.fhir_temporal_constraint
            start = EventNode(fresh("ka_start_event"), CFGEventType.START)
            timer = TimerEventNode(fresh("ka_timer_event"), CFGEventType.INTERMEDIATE,
                                  tc.to_event_temporal_constraint(action.id, TemporalCategory.KEEP_ALIVE_BOUND))
            end = EventNode(fresh("ka_end_event"), CFGEventType.END)
            for n in (start, timer, end):
                scope.add_node(n)
            add(scope, start.id, timer.id)
            add(scope, timer.id, end.id)

        def cycle_category(action):
            categories = action.fhir_temporal_constraint.get_categories()
            # A specific calendar schedule (e.g. every morning) takes priority
            # over the generic period, preserving the existing model behavior.
            if TemporalCategory.INSTANCE_CYCLE in categories:
                return TemporalCategory.INSTANCE_CYCLE
            return TemporalCategory.STANDARD_CYCLE

        def signature(action):
            payload = action.fhir_temporal_constraint.to_json()
            payload.pop("label", None)
            # Labels are presentation data; all timing/bound values must agree.
            for field in ("day_of_week", "time_of_day", "when"):
                payload[field] = sorted(payload[field] or [])
            return json.dumps(payload, sort_keys=True)

        actions = [n for n in cfg.nodes.values() if isinstance(n, ActionNode)
                   and n.fhir_temporal_constraint is not None]
        for action in actions:
            tc = action.fhir_temporal_constraint
            if tc.offset_duration is not None and (tc.event is not None or any(
                    category in tc.get_categories() for category in (TemporalCategory.STANDARD_CYCLE, TemporalCategory.INSTANCE_CYCLE, TemporalCategory.KEEP_ALIVE_BOUND))):
                raise ValueError("An exact/cyclic schedule combined with a relatedAction offset requires explicit activation semantics.")
        cycles = [n for n in actions if any(c in n.fhir_temporal_constraint.get_categories()
                   for c in (TemporalCategory.STANDARD_CYCLE, TemporalCategory.INSTANCE_CYCLE, TemporalCategory.KEEP_ALIVE_BOUND))]
        cycle_ids = {n.id for n in cycles}
        processed = set()
        units = []
        for action in cycles:
            if action.id in processed:
                continue
            group = [action]
            parent = action.incoming[0].source if len(action.incoming) == 1 else None
            if (isinstance(parent, GatewayNode)
                    and parent.gateway_class == CFGGatewayClass.PARALLEL
                    and parent.gateway_direction == CFGGatewayDirection.DIVERGENT):
                group = [e.target for e in parent.outgoing
                         if e.execution_condition is None
                         and e.target.id in cycle_ids
                         and len(e.target.incoming) == 1
                         and signature(e.target) == signature(action)]
            processed.update(n.id for n in group)
            shared_split = parent if len(group) > 1 and len(group) == len(parent.outgoing) else None
            entry = shared_split or action
            # Only a unique, unconditional initial flow can become the process
            # timer. An independently scheduled sibling must retain its block.
            root_edges = list(cfg.start_node.outgoing)
            whole_process = (len(root_edges) == 1
                             and root_edges[0].target is entry
                             and root_edges[0].execution_condition is None)
            units.append((group, shared_split, whole_process))

        # Plan and move the cycle regions before adding auxiliary timer lanes.
        # This avoids including Keep Alive edges in a later region discovery.
        global_cycle = None
        blocks = []
        for group, shared_split, whole_process in units:
            representative = group[0]
            tc = representative.fhir_temporal_constraint
            if whole_process:
                if global_cycle is not None:
                    raise ValueError("Multiple incompatible process-level cycles")
                global_cycle = representative
                continue

            if shared_split is not None:
                # Include matched gateway pairs and their continuation until
                # the surrounding join/end. Starting on a split opens depth 1.
                region = set()
                exits = set()
                stack = [(shared_split.id, 0)]
                seen = set()
                while stack:
                    nid, depth = stack.pop()
                    state = (nid, depth)
                    if state in seen:
                        continue
                    seen.add(state)
                    current = cfg.nodes[nid]
                    if isinstance(current, EventNode) and current.event_type == CFGEventType.END:
                        exits.add(nid)
                        continue
                    if isinstance(current, GatewayNode):
                        if current.gateway_direction == CFGGatewayDirection.DIVERGENT:
                            depth += 1
                        elif "conv_bound" not in current.id:
                            if depth == 0:
                                exits.add(nid)
                                continue
                            depth -= 1
                    if depth > len(cfg.nodes):
                        raise ValueError("Cycle region contains a control-flow loop")
                    region.add(nid)
                    stack.extend((e.target.id, depth) for e in current.outgoing)
                entry_id = shared_split.id
            else:
                paths = [p for member in group for p in cfg.find_all_bound_paths(member)]
                if not paths:
                    raise ValueError(f"No bounded paths for cycle {representative.id}")
                region = {nid for path in paths for nid in path}
                exits = {e.target.id for nid in region for e in cfg.nodes[nid].outgoing
                         if e.target.id not in region}
                entry_id = representative.id if len(group) == 1 else None

            if len(exits) != 1:
                raise ValueError(f"Cycle {representative.id} requires a single exit: {sorted(exits)}")
            if (region & cycle_ids) - {n.id for n in group}:
                raise ValueError(f"Cycle region {representative.id} includes another scheduled cycle")
            entering = [e for e in cfg.edges.values()
                        if e.source.id not in region and e.target.id in region]
            leaving = [e for e in cfg.edges.values()
                       if e.source.id in region and e.target.id not in region]
            internal = [e for e in cfg.edges.values()
                        if e.source.id in region and e.target.id in region]
            entries = {n.id for n in group} if entry_id is None else {entry_id}
            if not entering or any(e.target.id not in entries for e in entering):
                raise ValueError(f"Cycle {representative.id} has an external entry into its body")
            if any(e.execution_condition is not None for e in entering):
                raise ValueError("Conditional cycle entry needs explicit timer activation semantics")
            if len({e.source.id for e in entering}) != 1:
                raise ValueError("Cycle must have one external predecessor")
            block = BlockNode(fresh("block_node"))
            nodes_to_move = [cfg.nodes[nid] for nid in region]
            # Remove edges through the graph API before moving nodes, then
            # rebuild scope-local adjacency, including every branch exit.
            for edge in entering + leaving + internal:
                cfg.remove_edge(edge.id)
            for n in nodes_to_move:
                cfg.nodes.pop(n.id)
                block.add_node(n)
            for edge in internal:
                add(block, edge.source.id, edge.target.id, edge.relationship, edge.execution_condition)
            timer_start = TimerEventNode(fresh("block_timer_start_event"), CFGEventType.START,
                                        tc.to_event_temporal_constraint(representative.id, cycle_category(representative)))
            timer_end = EventNode(fresh("block_end_event"), CFGEventType.END)
            block.add_node(timer_start)
            block.add_node(timer_end)
            if entry_id is None:
                entry_gateway = GatewayNode(fresh("div_cycle"), CFGGatewayClass.PARALLEL,
                                            CFGGatewayDirection.DIVERGENT)
                block.add_node(entry_gateway)
                add(block, timer_start.id, entry_gateway.id)
                for member in group:
                    add(block, entry_gateway.id, member.id)
            else:
                add(block, timer_start.id, entry_id)
            if len(leaving) > 1:
                exit_gateway = GatewayNode(fresh("conv_cycle"), CFGGatewayClass.PARALLEL,
                                           CFGGatewayDirection.CONVERGENT)
                block.add_node(exit_gateway)
                for edge in leaving:
                    add(block, edge.source.id, exit_gateway.id, edge.relationship, edge.execution_condition)
                add(block, exit_gateway.id, timer_end.id)
            else:
                edge = leaving[0]
                add(block, edge.source.id, timer_end.id, edge.relationship, edge.execution_condition)
            cfg.add_node(block)
            before = entering[0]
            add(cfg, before.source.id, block.id, before.relationship, before.execution_condition)
            add(cfg, block.id, next(iter(exits)))
            blocks.append((block, representative))

        if global_cycle is not None:
            old = cfg.start_node
            timer_start = TimerEventNode(old.id, CFGEventType.START,
                          global_cycle.fhir_temporal_constraint.to_event_temporal_constraint(
                              global_cycle.id, cycle_category(global_cycle)))
            timer_start.incoming = list(old.incoming)
            timer_start.outgoing = list(old.outgoing)
            for edge in timer_start.incoming:
                edge.target = timer_start
            for edge in timer_start.outgoing:
                edge.source = timer_start
            cfg.nodes[old.id] = timer_start
            cfg.start_node = timer_start
            keep_alive(cfg, global_cycle)
        for block, representative in blocks:
            keep_alive(block, representative)

        # Apply action-level duration/iteration and non-cycle timers within
        # their owning scope, after moving cycle regions.
        def scopes(scope):
            yield scope
            for n in list(scope.nodes.values()):
                if isinstance(n, BlockNode):
                    yield from scopes(n)

        for scope in scopes(cfg):
            for node in list(scope.nodes.values()):
                if not isinstance(node, ActionNode) or node.fhir_temporal_constraint is None:
                    continue
                tc = node.fhir_temporal_constraint
                categories = tc.get_categories()
                node.temporal_constraints = [tc.to_event_temporal_constraint(node.id, category)
                    for category in (TemporalCategory.EXECUTION_ITERATION, TemporalCategory.EXECUTION_DURATION)
                    if category in categories]
                if node.temporal_constraints:
                    node.temporal_constraint = node.temporal_constraints[-1]
                is_cycle = node.id in cycle_ids
                category = None if is_cycle else next(
                    (c for c in (TemporalCategory.EXACT, TemporalCategory.OFFSET)
                     if c in categories), None)
                if category is not None:
                    timer = TimerEventNode(fresh("timer_node"), CFGEventType.INTERMEDIATE,
                                           tc.to_event_temporal_constraint(node.id, category))
                    incoming = list(node.incoming)
                    if not incoming:
                        raise ValueError(f"Timer action {node.id} has no predecessor")
                    scope.add_node(timer)
                    for edge in incoming:
                        scope.remove_edge(edge.id)
                        add(scope, edge.source.id, timer.id, edge.relationship, edge.execution_condition)
                    add(scope, timer.id, node.id)
                if TemporalCategory.EXECUTION_BOUND in categories:
                    # A durationMax limits this action; boundsDuration/Period
                    # are Keep Alive limits for scheduled cycles above.
                    if tc.duration_max is None:
                        continue
                    timer = TimerEventNode(fresh("boundary_node"), CFGEventType.BOUNDARY,
                                           tc.to_event_temporal_constraint(node.id, TemporalCategory.EXECUTION_BOUND))
                    join = GatewayNode(fresh("conv_bound"), CFGGatewayClass.EXCLUSIVE,
                                       CFGGatewayDirection.CONVERGENT)
                    outgoing = list(node.outgoing)
                    scope.add_node(timer)
                    scope.add_node(join)
                    for edge in outgoing:
                        scope.remove_edge(edge.id)
                        add(scope, join.id, edge.target.id, edge.relationship, edge.execution_condition)
                    add(scope, node.id, timer.id)
                    add(scope, node.id, join.id)
                    add(scope, timer.id, join.id)
        cfg.cfg_type = CFGType.TEMPORAL
        return cfg

    @staticmethod
    def from_json(json_payload: Dict[str, Any]) -> ControlFlowGraph:
        """
        Restore a CFG recursively, including nested blocks and concrete temporal constraints.

        :param json_payload: Serialized CFG with scope-local nodes, edges and root entry/exit IDs.
        :type json_payload: Dict[str, Any]
        :return: Independent CFG preserving metadata, adjacency order and edge identifiers.
        :rtype: ControlFlowGraph
        :raises ValueError: If node/edge identifiers, endpoints or adjacency are inconsistent.
        """
        import copy

        def resolve_node(payload):
            node_id, node_type = payload["id"], CFGNodeType(payload["node_type"])
            if node_type == CFGNodeType.BLOCK:
                block = BlockNode(node_id, payload.get("title"))
                populate_scope(block, payload)
                return block
            if node_type == CFGNodeType.ACTION:
                raw, constraint = payload.get("fhir_temporal_constraint"), payload.get("temporal_constraint")
                declarations = payload.get("temporal_constraints")
                return ActionNode(node_id, payload["title"], payload["activity_definition"],
                    FHIRTemporalConstraint.from_json(raw) if raw is not None else None,
                    TemporalConstraint.from_json(constraint) if constraint is not None else None,
                    copy.deepcopy(payload.get("attributes") or {}),
                    [TemporalConstraint.from_json(item) for item in declarations] if declarations is not None else None)
            if node_type == CFGNodeType.FAKE:
                return FakeNode(node_id)
            if node_type == CFGNodeType.GATEWAY:
                return GatewayNode(node_id, CFGGatewayClass(payload["gateway_class"]), CFGGatewayDirection(payload["gateway_direction"]))
            if node_type == CFGNodeType.EVENT:
                return EventNode(node_id, CFGEventType(payload["event_type"]))
            if node_type == CFGNodeType.TIMER_EVENT:
                if payload.get("temporal_constraint") is None:
                    raise ValueError(f"Timer {node_id} requires a temporal constraint.")
                return TimerEventNode(node_id, CFGEventType(payload["event_type"]),
                                      TemporalConstraint.from_json(payload["temporal_constraint"]))
            raise ValueError(f"Unsupported node type: {node_type}")

        def populate_scope(scope, payload):
            for key, node_payload in payload.get("nodes", {}).items():
                if key != node_payload["id"]:
                    raise ValueError(f"Inconsistent node ID: {key}")
                scope.add_node(resolve_node(node_payload))
            for key, edge_payload in payload.get("edges", {}).items():
                edge_id = edge_payload.get("id", key)
                if edge_id != key:
                    raise ValueError(f"Inconsistent edge ID: {key}")
                source, target = edge_payload["source"], edge_payload["target"]
                if source not in scope.nodes or target not in scope.nodes:
                    raise ValueError(f"Edge {key} references a node outside its scope.")
                condition = edge_payload.get("execution_condition")
                edge = CFGEdge(scope.nodes[source], scope.nodes[target], FHIRRelationshipType(edge_payload["relationship"]),
                               FHIRExecutionCondition.from_json(condition) if condition is not None else None)
                edge.id = edge_id
                scope.edges[edge.id] = edge
                edge.source.outgoing.append(edge)
                edge.target.incoming.append(edge)
            for key, node_payload in payload.get("nodes", {}).items():
                node = scope.nodes[key]
                for direction in ("incoming", "outgoing"):
                    if direction in node_payload:
                        serialized = node_payload[direction]
                        current = getattr(node, direction)
                        if len(serialized) != len(current) or set(serialized) != {edge.id for edge in current}:
                            raise ValueError(f"Inconsistent {direction} edges for node {key}")
                        setattr(node, direction, [scope.edges[edge_id] for edge_id in serialized])

        metadata = ("subject_id", "request_orchestration_id")
        is_instance = json_payload.get("graph_type") == "instance" or any(
            field in json_payload for field in metadata
        )
        graph_class = InstanceControlFlowGraph if is_instance else ControlFlowGraph
        instance_fields = {}
        if is_instance:
            if not all(json_payload.get(field) for field in metadata):
                raise ValueError("Instance CFG requires subject_id and request_orchestration_id")
            instance_fields = {field: json_payload[field] for field in metadata}
        cfg = graph_class(CFGType(json_payload["cfg_type"]), json_payload["id"], json_payload["version"],
                          json_payload["title"], json_payload["name"], json_payload["description"],
                          **instance_fields)
        populate_scope(cfg, json_payload)
        for field in ("start_node", "end_node"):
            node_id = json_payload.get(field)
            if node_id is not None and node_id not in cfg.nodes:
                raise ValueError(f"Unknown {field}: {node_id}")
            setattr(cfg, field, cfg.nodes.get(node_id))
        return cfg
