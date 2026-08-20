import glob, yaml, sys
CS = "niphr/cstemplate/.github/workflows/r-package.yml@8f8f2ad878710d6d9d3d5ee91ec7a566f8e34683"
RW = "raubreywhite/rwtemplate/.github/workflows/r-package.yml@bf26ed8e6e40309fc62b4179479c5475530df9f6"
fs = sorted(glob.glob('/home/raw996/niphr/cs*/.github/workflows/check-and-pkgdown.yml')
          + glob.glob('/home/raw996/wb/*/.github/workflows/check-and-pkgdown.yml'))
fs = [f for f in fs if '/cstemplate/' not in f and '/rwtemplate/' not in f and '/niphr/cs/' not in f]
assert len(fs) == 13, (len(fs), fs)
allow = {}  # Phase 5 removed both entries. They MUST NOT come back.

for f in fs:
    w = yaml.safe_load(open(f)); j = w['jobs']; trig = w.get(True, w.get('on'))
    assert 'workflow_dispatch' in trig, (f, 'no workflow_dispatch')
    assert trig['push']['branches'] == ['main', 'develop'], (f, 'push filter', trig['push'])
    assert trig['pull_request']['branches'] == ['main'], (f, 'pull_request filter', trig.get('pull_request'))
    call = [v for v in j.values() if 'uses' in v]
    assert len(call) == 1 and len(j) == 1, (f, 'expected one calling job')
    c = call[0]
    want = RW if f.startswith('/home/raw996/wb/') else CS
    assert c['uses'] == want, (f, 'wrong template or SHA', c['uses'])
    assert c.get('permissions', {}).get('contents') == 'write', (f, 'permissions', c.get('permissions'))
    assert (c.get('with') or {}).get('loc-allowlist') == allow.get(f), (f, 'allowlist', (c.get('with') or {}).get('loc-allowlist'))
print('13 callers wired correctly, exact template and SHA')
