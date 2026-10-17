"""Generate editable BPMN 2.0 XML and matching SVG previews. No dependencies."""

from html import escape
from pathlib import Path
from textwrap import wrap
import xml.etree.ElementTree as ET


HERE = Path(__file__).resolve().parent
BPMN = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI = "http://www.omg.org/spec/BPMN/20100524/DI"
DC = "http://www.omg.org/spec/DD/20100524/DC"
DI = "http://www.omg.org/spec/DD/20100524/DI"
for prefix, uri in (("bpmn", BPMN), ("bpmndi", BPMNDI), ("dc", DC), ("di", DI)):
    ET.register_namespace(prefix, uri)


AS_IS = {
    "title": "AS-IS · ручная обработка заявки",
    "width": 1270,
    "nodes": [
        ("start", "startEvent", "Заявка", 25, 117, 36, 36),
        ("receive", "task", "Прочитать входящую заявку", 90, 100, 145, 70),
        ("spreadsheet", "task", "Внести данные в таблицу", 270, 100, 145, 70),
        ("assigned", "exclusiveGateway", "Назначена?", 455, 110, 50, 50),
        ("contact", "task", "Связаться с клиентом", 545, 100, 145, 70),
        ("answer", "exclusiveGateway", "Ответил?", 730, 110, 50, 50),
        ("offer", "task", "Подготовить и отправить КП", 820, 100, 155, 70),
        ("decision", "exclusiveGateway", "Согласовано?", 1015, 110, 50, 50),
        ("won", "endEvent", "Успех", 1145, 117, 36, 36),
        ("lost_assignment", "endEvent", "Потеря заявки", 462, 275, 36, 36),
        ("lost_answer", "endEvent", "Нет контроля повтора", 737, 275, 36, 36),
        ("lost_offer", "endEvent", "Сделка не закрыта", 1022, 275, 36, 36),
    ],
    "flows": [
        ("start", "receive", ""), ("receive", "spreadsheet", ""),
        ("spreadsheet", "assigned", ""), ("assigned", "contact", "да"),
        ("assigned", "lost_assignment", "нет"), ("contact", "answer", ""),
        ("answer", "offer", "да"), ("answer", "lost_answer", "нет"),
        ("offer", "decision", ""), ("decision", "won", "да"),
        ("decision", "lost_offer", "нет"),
    ],
}

TO_BE = {
    "title": "TO-BE · управляемая CRM-воронка",
    "width": 1930,
    "nodes": [
        ("start", "startEvent", "Новая заявка", 25, 117, 36, 36),
        ("capture", "serviceTask", "Создать карточку CRM", 90, 100, 145, 70),
        ("dedupe", "serviceTask", "Проверить дубли", 270, 100, 145, 70),
        ("assign", "userTask", "Назначить ответственного", 450, 100, 145, 70),
        ("first_task", "serviceTask", "Создать задачу: 15 мин", 630, 100, 145, 70),
        ("contact", "userTask", "Первый контакт", 810, 100, 145, 70),
        ("qualified", "exclusiveGateway", "Подходит?", 995, 110, 50, 50),
        ("proposal", "userTask", "Подготовить КП", 1085, 100, 145, 70),
        ("follow_task", "serviceTask", "Создать задачу повтора", 1265, 100, 145, 70),
        ("follow", "userTask", "Повторный контакт", 1445, 100, 145, 70),
        ("decision", "exclusiveGateway", "Сделка?", 1630, 110, 50, 50),
        ("won", "endEvent", "Выиграна", 1795, 117, 36, 36),
        ("not_fit", "endEvent", "Причина отказа", 1002, 275, 36, 36),
        ("lost", "endEvent", "Проиграна", 1637, 275, 36, 36),
    ],
    "flows": [
        ("start", "capture", ""), ("capture", "dedupe", ""),
        ("dedupe", "assign", ""), ("assign", "first_task", ""),
        ("first_task", "contact", ""), ("contact", "qualified", ""),
        ("qualified", "proposal", "да"), ("qualified", "not_fit", "нет"),
        ("proposal", "follow_task", ""), ("follow_task", "follow", ""),
        ("follow", "decision", ""), ("decision", "won", "да"),
        ("decision", "lost", "нет"),
    ],
}


def geometry(node):
    _, _, _, x, y, w, h = node
    return x, y, w, h


def route(a, b):
    ax, ay, aw, ah = geometry(a)
    bx, by, bw, bh = geometry(b)
    if by > ay + 80:
        return [(ax + aw / 2, ay + ah), (bx + bw / 2, by)]
    return [(ax + aw, ay + ah / 2), (bx, by + bh / 2)]


def build_bpmn(name, spec):
    root = ET.Element(f"{{{BPMN}}}definitions", {
        "id": f"Definitions_{name}",
        "targetNamespace": "https://github.com/iwik1329/Pulse-crm/process",
    })
    process = ET.SubElement(root, f"{{{BPMN}}}process", {"id": f"Process_{name}", "name": spec["title"], "isExecutable": "false"})
    nodes = {node[0]: node for node in spec["nodes"]}
    for node_id, kind, label, *_ in spec["nodes"]:
        ET.SubElement(process, f"{{{BPMN}}}{kind}", {"id": f"Node_{node_id}", "name": label})
    for i, (source, target, label) in enumerate(spec["flows"], 1):
        ET.SubElement(process, f"{{{BPMN}}}sequenceFlow", {
            "id": f"Flow_{i}", "sourceRef": f"Node_{source}", "targetRef": f"Node_{target}", **({"name": label} if label else {}),
        })
    diagram = ET.SubElement(root, f"{{{BPMNDI}}}BPMNDiagram", {"id": f"Diagram_{name}"})
    plane = ET.SubElement(diagram, f"{{{BPMNDI}}}BPMNPlane", {"id": f"Plane_{name}", "bpmnElement": f"Process_{name}"})
    for node in spec["nodes"]:
        node_id, _, _, x, y, w, h = node
        shape = ET.SubElement(plane, f"{{{BPMNDI}}}BPMNShape", {"id": f"Shape_{node_id}", "bpmnElement": f"Node_{node_id}"})
        ET.SubElement(shape, f"{{{DC}}}Bounds", {"x": str(x), "y": str(y), "width": str(w), "height": str(h)})
    for i, (source, target, _) in enumerate(spec["flows"], 1):
        edge = ET.SubElement(plane, f"{{{BPMNDI}}}BPMNEdge", {"id": f"Edge_{i}", "bpmnElement": f"Flow_{i}"})
        for x, y in route(nodes[source], nodes[target]):
            ET.SubElement(edge, f"{{{DI}}}waypoint", {"x": str(x), "y": str(y)})
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(HERE / f"{name}.bpmn", encoding="utf-8", xml_declaration=True)


def build_svg(name, spec):
    nodes = {node[0]: node for node in spec["nodes"]}
    width = spec["width"]
    parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 370" role="img" aria-labelledby="title">
<title id="title">{escape(spec["title"])}</title>
<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#6d819b"/></marker></defs>
<style>text{{font-family:Arial,sans-serif;fill:#233b5b}}.label{{font-size:16px;font-weight:600}}.edge{{stroke:#6d819b;stroke-width:2;fill:none;marker-end:url(#arrow)}}.flowlabel{{font-size:15px;fill:#5f7592;font-weight:700}}.task{{fill:#fff;stroke:#77a6d8;stroke-width:2}}.service{{fill:#e8f3ff;stroke:#2875d6;stroke-width:2}}.event{{fill:#fff;stroke:#2772cf;stroke-width:2.5}}.end{{fill:#fff;stroke:#2571cc;stroke-width:4}}.loss{{stroke:#e25b6a}}.gateway{{fill:#fff4db;stroke:#e3a431;stroke-width:2}}</style>
<rect width="100%" height="100%" fill="#f8fbff"/><text x="25" y="36" style="font-size:22px;font-weight:700">{escape(spec["title"])}</text>
<text x="25" y="60" style="font-size:12px;fill:#7186a2">BPMN 2.0 · события, задачи, развилки и потоки</text>''']
    for source, target, label in spec["flows"]:
        (x1,y1),(x2,y2)=route(nodes[source],nodes[target])
        parts.append(f'<path class="edge" d="M{x1} {y1} L{x2} {y2}"/>')
        if label:
            parts.append(f'<text class="flowlabel" x="{(x1+x2)/2}" y="{(y1+y2)/2-7}">{escape(label)}</text>')
    for node_id, kind, label, x, y, w, h in spec["nodes"]:
        if kind in ("startEvent", "endEvent"):
            klass = "end loss" if node_id.startswith("lost") or node_id=="not_fit" else "end" if kind=="endEvent" else "event"
            parts.append(f'<circle class="{klass}" cx="{x+w/2}" cy="{y+h/2}" r="{w/2-2}"/>')
            if kind=="startEvent": parts.append(f'<text x="{x+w/2}" y="{y+h+23}" text-anchor="middle" class="label">{escape(label)}</text>')
            else: parts.append(f'<text x="{x+w/2}" y="{y+h+23}" text-anchor="middle" class="label">{escape(label)}</text>')
        elif kind=="exclusiveGateway":
            parts.append(f'<path class="gateway" d="M{x+w/2} {y} L{x+w} {y+h/2} L{x+w/2} {y+h} L{x} {y+h/2} Z"/>')
            parts.append(f'<text x="{x+w/2}" y="{y+h+22}" text-anchor="middle" class="label">{escape(label)}</text>')
        else:
            klass = "service" if kind=="serviceTask" else "task"
            parts.append(f'<rect class="{klass}" x="{x}" y="{y}" width="{w}" height="{h}" rx="13"/>')
            lines = wrap(label, width=17)
            for j, line in enumerate(lines):
                parts.append(f'<text class="label" x="{x+w/2}" y="{y+h/2+(j-(len(lines)-1)/2)*17+4}" text-anchor="middle">{escape(line)}</text>')
    parts.append('</svg>')
    (HERE / f"{name}.svg").write_text("\n".join(parts), encoding="utf-8")


if __name__ == "__main__":
    for diagram_name, spec in (("as-is", AS_IS), ("to-be", TO_BE)):
        build_bpmn(diagram_name, spec)
        build_svg(diagram_name, spec)
