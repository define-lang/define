from __future__ import annotations

import xml.etree.ElementTree as ET  # noqa: S405 - It parses only the test's XML.

from tools.windows_vm import deploy_rbe

_DEFINITION = """\
<domain type='kvm'>
  <name>define-windows</name>
  <devices>
    <interface type='user'>
      <mac address='52:54:00:b8:90:67'/>
      <portForward proto='tcp' address='127.0.0.1'>
        <range start='2222' to='22'/>
      </portForward>
      <portForward proto='tcp' address='::1'>
        <range start='2222' to='22'/>
      </portForward>
      <model type='virtio'/>
      <backend type='passt'/>
    </interface>
  </devices>
</domain>
"""


def test_adds_forwards_bound_to_localhost():
    updated = deploy_rbe.add_rbe_port_forward(_DEFINITION, 2223)

    assert updated is not None
    interface = ET.fromstring(updated).find("devices/interface")  # noqa: S314
    assert interface is not None
    children: list[tuple[str, str | None, list[tuple[str | None, str | None]]]] = []
    for child in interface:
        ranges: list[tuple[str | None, str | None]] = []
        for port_range in child.iterfind("range"):
            ranges.append((port_range.get("start"), port_range.get("to")))
        children.append((child.tag, child.get("address"), ranges))
    assert children == [
        ("mac", "52:54:00:b8:90:67", []),
        ("portForward", "127.0.0.1", [("2222", "22")]),
        ("portForward", "::1", [("2222", "22")]),
        ("model", None, []),
        ("backend", None, []),
        ("portForward", "127.0.0.1", [("2223", "8980")]),
        ("portForward", "::1", [("2223", "8980")]),
    ]


def test_leaves_a_definition_that_already_forwards_the_port():
    updated = deploy_rbe.add_rbe_port_forward(_DEFINITION, 2223)
    assert updated is not None

    assert deploy_rbe.add_rbe_port_forward(updated, 2223) is None
