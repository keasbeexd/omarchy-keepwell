"""UFW's rules, read from its own files, for the Firewall check and for
"Remove firewall rules".

The rule files are the only place outside the action table that reaches a
root command's arguments, so nothing is passed on loosely: every field of a
rule has to match what ufw itself writes, or the rule is counted but never
offered for removal. Application, routed, interface and logged rules are
left to ufw too. A comment is only ever shown, never put in a command.
"""

import hashlib
import ipaddress
import re

from keepwell_unclaimed import UNSAFE_TEXT

MAX_LISTED = 64
ACTIONS = ("allow", "deny", "reject", "limit")
PROTOS = ("tcp", "udp", "any")
DIRECTIONS = ("in", "out")
ANY = ("0.0.0.0/0", "::/0")
PORTS = re.compile(r"[0-9]{1,5}(?:[:,][0-9]{1,5}){0,29}")
ADDRESS = re.compile(r"[0-9a-fA-F:.]{2,39}(?:/[0-9]{1,3})?")
COMMENT_CHARS = 60


def _port(text):
    return text == "any" or (PORTS.fullmatch(text) is not None
                             and all(1 <= int(n) <= 65535 for n in re.split("[:,]", text)))


def _address(text):
    if ADDRESS.fullmatch(text) is None:
        return False
    try:
        ipaddress.ip_network(text, strict=False)
    except ValueError:
        return False
    return True


def _comment(raw):
    try:
        text = bytes.fromhex(raw).decode("utf-8", "replace")
    except ValueError:
        return ""
    return UNSAFE_TEXT.sub("", text).strip()[:COMMENT_CHARS]


def _tuples(raw):
    """(fields, comment) of each rule in one of ufw's rule files."""
    for line in (raw or b"").decode("ascii", "replace").splitlines():
        if line.startswith("### tuple ### "):
            body, _, comment = line[len("### tuple ### "):].partition(" comment=")
            yield body.split(), comment.strip()


def _parse(fields, comment, family):
    """One rule as a dict. Its "plain" is false unless ufw can be told to
    delete it from these fields alone."""
    rule = {"plain": False, "family": family, "fields": fields, "comment": _comment(comment)}
    if len(fields) != 7:
        return rule
    action, proto, dport, dst, sport, src, direction = fields
    if action in ACTIONS and proto in PROTOS and direction in DIRECTIONS \
            and _port(dport) and _port(sport) and _address(dst) and _address(src):
        rule["plain"] = True
    return rule


def _finish(rule):
    action, proto, dport, dst, sport, src, direction = rule["fields"]
    family = rule["family"]
    wide = src in ANY and dst in ANY
    # "from any to any" means both families, so a rule on only one keeps its
    # literal addresses. With one specific address, that address sets the family.
    from_ = "any" if src in ANY and (family == "both" or not wide) else src
    to = "any" if dst in ANY and (family == "both" or not wide) else dst
    argv = ["delete", action] + (["out"] if direction == "out" else []) + ["from", from_]
    argv += (["port", sport] if sport != "any" else []) + ["to", to]
    argv += ["port", dport] if dport != "any" else []
    argv += ["proto", proto] if proto != "any" else []

    what = "all ports" if dport == "any" else ("port " + dport if proto == "any" else dport + "/" + proto)
    what = what.replace(":", "–")
    label = action.capitalize() + " " + ("outgoing " if direction == "out" else "") + what
    label += " from " + ("anywhere" if src in ANY else src)
    if sport != "any":
        label += " port " + sport.replace(":", "–")
    if dst not in ANY:
        label += " to " + dst
    notes = [rule["comment"]] if rule["comment"] else []
    if wide and family != "both":
        notes.append("IPv6 only" if family == "v6" else "IPv4 only")
    rule.update(argv=argv, label=label, hint=" · ".join(notes),
                id="r" + hashlib.sha256((family + " " + " ".join(rule["fields"])).encode()).hexdigest()[:16])
    return rule


def rules(v4, v6):
    """Every rule in the two files' bytes. ufw stores one "anywhere" rule
    twice, once for IPv4 and once for IPv6, and deleting either form with
    "any" removes both, so those count as one."""
    out, wide = [], {}
    for raw, family in ((v4, "v4"), (v6, "v6")):
        for fields, comment in _tuples(raw):
            rule = _parse(fields, comment, family)
            key = None
            if rule["plain"] and fields[3] in ANY and fields[5] in ANY:
                key = (fields[0], fields[1], fields[2], fields[4], fields[6])
            twin = wide.get(key)
            if twin is not None and twin["family"] != family:
                twin["family"] = "both"
                twin["comment"] = twin["comment"] or rule["comment"]
                continue
            if key is not None:
                wide[key] = rule
            out.append(rule)
    return [_finish(r) if r["plain"] else r for r in out]


def removable(v4, v6):
    return [r for r in rules(v4, v6) if r["plain"]][:MAX_LISTED]
