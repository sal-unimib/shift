from __future__ import annotations

# import shw_service.model.bpmn as bpmn_model
# from shw_service.sources.ontology import OntologySource
from typing import Any

import owlready2 as or2
from fhir.resources.plandefinition import PlanDefinition


class CFGNode:
    """
    Represents a node in the therapeutic plan graph intermediate representation.
    """

    id: str
    """Node identifier."""

    title: str | None
    description: str | None
    action_definition_id: str | None
    variables: dict[str, str]

    bpmn_element: or2.ThingClass

    incoming: list[CFGEdge]
    """List of incoming edges."""
    outgoing: list[CFGEdge]
    """List of outgoing edges."""
    attributes: dict[str, str]
    """Key-value attributes for transformation."""  # TODO riscrivere

    # def __init__(self, id: str, **attrs: Any):
    def __init__(
        self,
        id: str,
        bpmn_element: or2.ThingClass,
        title: str | None = None,
        description: str | None = None,
        action_definition_id: str | None = None,
    ):
        self.id = id
        self.title = title
        self.description = description
        self.action_definition_id = action_definition_id
        self.bpmn_element = bpmn_element
        self.outgoing: list[CFGEdge] = []
        self.incoming: list[CFGEdge] = []
        # self.variables = {}
        self.attributes = {}
        # TODO elencare (in docs gli attributi utili)

    def successors(self) -> list[CFGNode]:
        successors = []
        for e in self.outgoing:
            successors.append(e.target)
        return successors

    def predecessors(self) -> list[CFGNode]:
        predecessors = []
        for e in self.incoming:
            predecessors.append(e.source)
        return predecessors


class EdgeCondition:
    expression: str
    label: str | None
    name: str | None

    def __init__(
        self,
        expression: str,
        label: str | None = None,
        name: str | None = None,
    ):
        self.expression = expression
        self.label = label
        self.name = name

    def to_formal_expression(self) -> bpmn_model.FormalExpression:
        return bpmn_model.FormalExpression(content=[self.expression])


class CFGEdge:
    """
    Represents an edge in the therapeutic plan graph intermediate representation.
    """

    id: str
    """Edge identifier. It is generated as a combination of source and target node identifiers: \<source\>\_to\_\<target\>."""
    attributes: dict[str, str]
    """Key-value attributes for transformation."""  # TODO rifare
    label: str | None
    condition: EdgeCondition | None
    source: CFGNode
    target: CFGNode

    def __init__(
        self,
        source: CFGNode,
        target: CFGNode,
        condition: EdgeCondition | None = None,
        **attrs: Any,
    ):
        self.id = source.id + "_to_" + target.id
        self.source = source
        self.target = target
        self.condition = condition
        self.attributes = dict(attrs)
        # TODO elencare (in docs gli attributi utili)


class SESERegion:
    entry: CFGNode
    exit: CFGNode
    body: set[CFGNode]

    def __init__(self, entry: CFGNode, exit: CFGNode, body: set[CFGNode]):
        self.entry = entry
        self.exit = exit
        self.body = body

    def nodes(self) -> set[CFGNode]:
        return self.body.union({self.entry, self.exit})

    def contains(self, other_region: SESERegion) -> bool:
        return other_region.nodes().issubset(self.nodes())

    def size(self) -> int:
        return len(self.nodes())

    def validate(self) -> bool:
        for n in self.nodes():
            for e in n.incoming:
                if e.source not in self.nodes() and n != self.entry:
                    return False
        for n in self.nodes():
            for e in n.outgoing:
                if e.target not in self.nodes() and n != self.exit:
                    return False
        return True

    def edges(self) -> dict[str, CFGEdge]:
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

    def to_subgraph(self) -> ControlFlowGraph:
        cfg = ControlFlowGraph(
            f"sese_subgraph_{self.entry.id}-{self.exit.id}",
            f"sese_subgraph_{self.entry.id}-{self.exit.id}",
            f"SESE Region Subgraph ({self.entry.id}-{self.exit.id})",
        )
        cfg.create_node(
            id=self.entry.id,
            title=self.entry.title,
            bpmn_element=self.entry.bpmn_element,
            description=self.entry.description,
            action_definition_id=self.entry.action_definition_id,
            start=True,
        )
        cfg.create_node(
            id=self.exit.id,
            title=self.exit.title,
            bpmn_element=self.exit.bpmn_element,
            description=self.exit.description,
            action_definition_id=self.exit.action_definition_id,
            end=True,
        )
        for n in self.body:
            cfg.create_node(
                id=n.id,
                title=n.title,
                bpmn_element=n.bpmn_element,
                description=n.description,
                action_definition_id=n.action_definition_id,
            )
        for e in self.edges().values():
            cfg.add_edge(
                src=e.source.id, tgt=e.target.id, condition=e.condition
            )

        return cfg

    def is_maximal(self, cfg: ControlFlowGraph) -> bool:
        return (
            self.entry == cfg.start_node
            and self.exit == cfg.end_node
            and self.nodes() == set(cfg.nodes.values())
        )

    def __str__(self):
        # return f"[{self.entry.id} - {self.exit.id} => {'-'.join([n.id for n in self.body])}]"
        return f'Region(start="{self.entry.id}", end="{self.exit.id}", body=["{'", "'.join([n.id for n in self.body])}"])'


class ControlFlowGraph:
    """
    Represents a graph structure of the therapeutic plan.
    It contains nodes and edges, defined from a FHIR PlanDefinition resource or derived from them.
    """

    id: str
    """Therapeutic plan graph identifier. Corresponds to 'id' field in FHIR PlanDefinition."""
    name: str | None
    """Plan definition machine-readable name. Corresponds to 'name' field in FHIR PlanDefinition."""
    title: str | None
    """Plan definition human-readable title. Corresponds to 'title' field in FHIR PlanDefinition."""
    description: str | None
    """Plan definition human-readable description. Corresponds to 'description' field in FHIR PlanDefinition."""
    version: str
    """Plan definition version. Corresponds to 'version' field in FHIR PlanDefinition."""
    start_node: CFGNode | None
    """Starting node of the graph."""
    end_node: CFGNode | None
    """Ending node of the graph."""
    nodes: dict[str, CFGNode]
    """Map of all nodes in the therapeutic plan graph, with node identifier as key and CFGNode instance as value."""
    edges: dict[str, CFGEdge]
    """Map of all edges in the therapeutic plan graph, with edge identifier as key and CFGEdge instance as value."""

    def __init__(
        self,
        id: str,
        version: str,
        title: str | None = None,
        name: str | None = None,
        description: str | None = None,
    ):
        self.id = id
        self.version = version
        self.title = title
        self.name = name
        self.description = description
        self.nodes = {}
        self.edges = {}
        self.start_node = None
        self.end_node = None

    def create_node(
        self,
        id: str,
        bpmn_element: or2.ThingClass,
        title: str | None = None,
        description: str | None = None,
        action_definition_id: str | None = None,
        start: bool = False,
        end: bool = False,
    ) -> CFGNode | None:
        # TODO docstring
        if id not in self.nodes:
            new_node = CFGNode(
                id=id,
                title=title,
                description=description,
                action_definition_id=action_definition_id,
                bpmn_element=bpmn_element,
            )
            self.nodes[id] = new_node
            if start:
                self.start_node = new_node
            if end:
                self.end_node = new_node
            return new_node

    def add_edge(
        self, src: str, tgt: str, condition: EdgeCondition | None = None
    ) -> CFGEdge | None:
        # TODO docstring
        e_id = src + "_to_" + tgt
        if src in self.nodes and tgt in self.nodes and e_id not in self.edges:
            s = self.nodes.get(src)
            t = self.nodes.get(tgt)
            e = CFGEdge(source=s, target=t, condition=condition)
            self.edges[e_id] = e
            s.outgoing.append(e)
            t.incoming.append(e)
            return e

    # TODO dominators
    def dominators(self) -> dict[CFGNode, set[CFGNode]]:
        nodes = set(self.nodes.values())
        start = self.start_node

        dom: dict[CFGNode, set[CFGNode]] = {}
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

    # TODO post-dominators
    def postdominators(self) -> dict[CFGNode, set[CFGNode]]:
        nodes = set(self.nodes.values())
        end = self.end_node

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

    # TODO SESE Regions
    def sese_regions(self) -> list[SESERegion]:
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

    # TODO SubGraph
    def subgraph(self, start: str, end: str) -> ControlFlowGraph | None:

        # reachability check
        def _reachable_from(start: CFGNode) -> set[str]:
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

        def _can_reach(end: CFGNode) -> set[str]:
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
            return
        start_node = self.nodes[start]
        end_node = self.nodes[end]

        forward = _reachable_from(start_node)
        backward = _can_reach(end_node)
        sub_nodes_ids = forward.intersection(backward)
        if start not in sub_nodes_ids or end not in sub_nodes_ids:
            return

        sub = ControlFlowGraph(
            id=f"{self.id}_sub_{start}_{end}",  # TODO sistemare
            version=self.version,
            name=self.name,
            title=self.title,
        )
        for nid in sub_nodes_ids:
            node = self.nodes[nid]
            sub.create_node(  # TODO sistemare
                id=node.id,
                bpmn_element=node.bpmn_element,
                title=node.title,
                description=node.description,
                action_definition_id=node.action_definition_id,
                start=(nid == start),
                end=(nid == end),
            )
        for edge in self.edges.values():
            s_id = edge.source.id
            t_id = edge.target.id
            if s_id in sub_nodes_ids and t_id in sub_nodes_ids:
                sub.add_edge(src=s_id, tgt=t_id, condition=edge.condition)
        return sub

    # TODO SESE RegionsTree
    def sese_region_tree(self) -> dict[SESERegion, list[SESERegion]]:
        regions = self.sese_regions()

        # 1️⃣ containment completo
        tree: dict[SESERegion, list[SESERegion]] = {r: [] for r in regions}
        for r1 in regions:
            for r2 in regions:
                if r1 != r2 and r1.contains(r2):
                    tree[r1].append(r2)

        # 2️⃣ riduzione transitiva
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

    # TODO Clone
    # TODO replace_node (end/start ... substitution/append)
    def replace_end_node(
        self,
        id: str,
        bpmn_element: or2.ThingClass,
        title: str | None = None,
        description: str | None = None,
        action_definition_id: str | None = None,
    ):
        old_end = self.end_node
        edge_to_remove = list(old_end.incoming)

        for e in edge_to_remove:
            e.source.outgoing.remove(e)
            old_end.incoming.remove(e)
            del self.edges[e.id]

        del self.nodes[old_end.id]

        self.create_node(
            id=id,
            bpmn_element=bpmn_element,
            title=title,
            description=description,
            action_definition_id=action_definition_id,
            end=True,
        )
        for e in edge_to_remove:
            self.add_edge(src=e.source.id, tgt=id, condition=e.condition)

    # TODO
    @classmethod
    def from_plandefinition(cls, pd: PlanDefinition) -> ControlFlowGraph:
        bbo = OntologySource().bbo
        cfg = cls(
            id=pd.id,
            version=pd.version,
            title=pd.title,
            name=pd.name,
            description=pd.description,
        )

        for action in pd.action or []:
            node = cfg.create_node(
                id=action.linkId,
                title=action.title,
                description=action.description,
                action_definition_id=action.definitionCanonical.split("/")[-1],
                bpmn_element=bbo.Task,
            )
            if node:
                for dynamic_value in action.dynamicValue or []:
                    node.attributes[dynamic_value.path] = (
                        dynamic_value.expression.expression
                    )
            else:
                print("qualcosa non va")

        pred_nodes = set()
        for action in pd.action or []:
            for related_action in action.relatedAction or []:
                # if relatedAction.relationship == 'after-end'
                edge = cfg.add_edge(
                    src=related_action.targetId, tgt=action.linkId
                )
                pred_nodes.add(related_action.targetId)
                if edge:
                    if action.condition:
                        # TODO per ora prendo solo la prima (assumo che ce ne sia solo una)
                        edge.condition = EdgeCondition(
                            expression=action.condition[
                                0
                            ].expression.expression,
                            label=action.condition[0].expression.name,
                            description=action.condition[
                                0
                            ].expression.description,
                        )

        # 4. Create start node and edges (actions without relatedAction)
        start_id = "start_node"
        cfg.create_node(id=start_id, bpmn_element=bbo.StartEvent, start=True)
        starting_actions = [
            action for action in pd.action if not action.relatedAction
        ]
        for action in starting_actions:
            edge = cfg.add_edge(src=start_id, tgt=action.linkId)
            if edge:
                if action.condition:
                    # TODO per ora prendo solo la prima (assumo che ce ne sia solo una)
                    edge.condition = EdgeCondition(
                        expression=action.condition[0].expression.expression,
                        label=action.condition[0].expression.description,
                        name=action.condition[0].expression.name,
                    )

        # 5. Create end node and edges (nodes without outgoing edges)
        end_id = "end_node"
        cfg.create_node(id=end_id, bpmn_element=bbo.EndEvent, end=True)
        ending_nodes = [
            n
            for n in cfg.nodes.values()
            if n.id not in (cfg.start_node.id, cfg.end_node.id)
            and n.id not in pred_nodes
        ]
        for node in ending_nodes:
            cfg.add_edge(
                src=node.id, tgt=end_id
            )  # TODO devo considerare possibili conditions?

        return cfg
