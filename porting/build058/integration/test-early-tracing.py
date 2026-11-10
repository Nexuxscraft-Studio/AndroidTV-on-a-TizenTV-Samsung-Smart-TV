#!/usr/bin/env python3
"""Host-only contract tests; do not need ARM compiler or proprietary archive."""
import importlib.util
import pathlib
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).with_name("port-early-tracing.py")
spec = importlib.util.spec_from_file_location("early_trace", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class EarlyTracingTests(unittest.TestCase):
    def test_exact_change(self):
        source = '#include <trace/early.h>\nvoid f(void) { trace_early_message(msg); }\n'
        result = module.transform(source)
        self.assertIn('pr_debug("%s", msg);', result)
        self.assertNotIn('#include <trace/early.h>', result)
    def test_missing_call_fails_closed(self):
        with self.assertRaises(ValueError):
            module.transform('#include <trace/early.h>\n')
    def test_duplicate_call_fails_closed(self):
        with self.assertRaises(ValueError):
            module.transform('#include <trace/early.h>\ntrace_early_message(msg); trace_early_message(msg);')
if __name__ == "__main__":
    unittest.main()
