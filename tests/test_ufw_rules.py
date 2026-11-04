"""Firewall rules, from ufw's files to the delete command: only well-formed
plain rules are offered, and each command must parse, in ufw's own parser,
to exactly the rule it was built from. Skips that half if ufw isn't here.

Run: python3 tests/test_ufw_rules.py
"""

import gettext
import glob
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bin"))
import keepwell_ufw as k  # noqa: E402

comment = "cloudroll dev server".encode().hex()
V4 = f"""# not a rule
### tuple ### allow udp 53317 0.0.0.0/0 any 0.0.0.0/0 in
### tuple ### allow tcp 53317 0.0.0.0/0 any 0.0.0.0/0 in
### tuple ### allow udp 53 172.17.0.1 any 172.16.0.0/12 in comment=616c6c6f772d646f636b65722d646e73
### tuple ### allow tcp 8443 0.0.0.0/0 any 192.168.1.0/24 in comment={comment}
### tuple ### deny tcp 80,443 0.0.0.0/0 any 0.0.0.0/0 in
### tuple ### limit tcp 22 0.0.0.0/0 any 0.0.0.0/0 in
### tuple ### reject tcp 6000:6007 0.0.0.0/0 any 10.0.0.0/8 out
### tuple ### allow any any 10.1.2.3 any 0.0.0.0/0 in
### tuple ### allow tcp 25 0.0.0.0/0 2525 0.0.0.0/0 in
""".encode()
V6 = b"""### tuple ### allow udp 53317 ::/0 any ::/0 in
### tuple ### allow tcp 53317 ::/0 any ::/0 in
### tuple ### deny tcp 9000 ::/0 any 2001:db8::/32 in
### tuple ### allow tcp 9001 ::/0 any ::/0 in
"""
# Counted, never offered: the last ones try to smuggle something in.
LEFT_ALONE = b"""### tuple ### allow tcp 80 0.0.0.0/0 any 0.0.0.0/0 Apache - in
### tuple ### route:allow tcp 80 0.0.0.0/0 any 0.0.0.0/0 in
### tuple ### allow_log tcp 81 0.0.0.0/0 any 0.0.0.0/0 in
### tuple ### allow tcp 82 0.0.0.0/0 any 0.0.0.0/0 in_eth0
### tuple ### allow esp any 0.0.0.0/0 any 0.0.0.0/0 in
### tuple ### allow tcp --force 0.0.0.0/0 any 0.0.0.0/0 in
### tuple ### allow tcp 83 -1.2.3.4 any 0.0.0.0/0 in
### tuple ### allow tcp 70000 0.0.0.0/0 any 0.0.0.0/0 in
### tuple ### allow tcp 84 0.0.0.0/0;reboot any 0.0.0.0/0 in
### tuple ### disable tcp 85 0.0.0.0/0 any 0.0.0.0/0 in
"""

failed = []


def expect(ok, what):
    if not ok:
        failed.append(what)


found = k.removable(V4, V6)
labels = {r["label"]: r for r in found}
expect(len(found) == 11, f"expected 11 removable rules, got {len(found)}: {sorted(labels)}")
expect(len({r["id"] for r in found}) == len(found), "ids repeat")
expect(labels.get("Allow 53317/udp from anywhere", {}).get("argv")
       == ["delete", "allow", "from", "any", "to", "any", "port", "53317", "proto", "udp"], "merged rule")
expect(labels.get("Allow 8443/tcp from 192.168.1.0/24", {}).get("hint") == "cloudroll dev server", "comment")
expect(labels.get("Allow 9001/tcp from anywhere", {}).get("hint") == "IPv6 only", "lone v6 rule")
expect("Deny 80,443/tcp from anywhere" in labels, "multiport label")
expect(all(__import__("re").fullmatch("[a-z0-9]{1,24}", r["id"]) for r in found), "id form --with accepts")

mixed = k.rules(LEFT_ALONE, b"")
expect(len(mixed) == 10, "unusual rules still counted")
expect(not any(r["plain"] for r in mixed), f"offered: {[r['fields'] for r in mixed if r['plain']]}")
expect(k.removable(V4 * 20, b"")[k.MAX_LISTED - 1:] != [] and len(k.removable(V4 * 20, b"")) == k.MAX_LISTED, "cap")
expect(k.rules(None, None) == [], "missing files")
hostile = b"### tuple ### allow tcp 22 0.0.0.0/0 any 0.0.0.0/0 in comment=" + "\x1b[31mhi‮\n".encode().hex().encode()
expect(k.rules(hostile, b"")[0]["comment"] == "[31mhi", "control characters in a comment")

sites = glob.glob("/usr/lib/python3*/site-packages")
checked = 0
if glob.glob("/usr/lib/python3*/site-packages/ufw/parser.py"):
    sys.path.extend(sites)
    gettext.install("ufw")
    import ufw.frontend  # noqa: E402

    def back(argv):
        r = ufw.frontend.parse_command(["ufw"] + argv).data["rule"]
        return r, ufw.frontend.parse_command(["ufw"] + argv).data["iptype"]

    for rule in found:
        r, iptype = back(rule["argv"])
        action, proto, dport, dst, sport, src, direction = rule["fields"]
        got = (r.action, r.protocol, r.dport, r.sport, r.direction, r.remove)
        want = (action, proto, dport, sport, direction, True)
        expect(got == want, f"{rule['label']}: {got} != {want}")
        expect(iptype == rule["family"], f"{rule['label']}: family {iptype} != {rule['family']}")
        for mine, theirs in ((src, r.src), (dst, r.dst)):
            expect(theirs == mine or (mine in k.ANY and theirs in k.ANY), f"{rule['label']}: {mine} != {theirs}")
        checked += 1
else:
    print("ufw isn't installed: skipped the check against its parser")

if failed:
    print("\n".join(failed))
    sys.exit(1)
print(f"ok: {len(found)} rules offered, {len(mixed)} left to ufw, {checked} commands checked against ufw's parser")
