"""Compile actual genpd callback source against a host MMIO model."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PATCH = REPO / 'porting/build059/kernel/patches/0022-clk-sdp1804-gpu-genpd-sequencing.patch'


def added_file(patch, path):
    block = patch.split('+++ b/' + path + '\n', 1)[1].split('diff --git ', 1)[0]
    return ''.join(line[1:] for line in block.splitlines(True)
                   if line.startswith('+') and not line.startswith('+++'))


class GpuPowerTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'host C compiler required')
    def test_actual_callbacks_sequence_and_rollback(self):
        src = added_file(PATCH.read_text(), 'drivers/clk/clk-sdp1804-gpu.c')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Replace kernel type/API headers with the host model, retaining
            # the actual driver functions and register operations unchanged.
            for header in re.findall(r'#include [<"]([^>"]+)', src):
                p = root / header
                p.parent.mkdir(parents=True, exist_ok=True)
                if header == "linux/errno.h":
                    p.write_text("#include_next <linux/errno.h>\n")
                else:
                    p.touch()
            (root / 'clk-sdp1804-gpu.c').write_text(src)
            shutil.copyfile(HERE / 'gpu_power_harness.c', root / 'test.c')
            subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                            '-I', tmp, str(root/'test.c'), '-o', str(root/'test')], check=True)
            subprocess.run([str(root/'test')], check=True)
