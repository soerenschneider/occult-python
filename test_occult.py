from unittest import TestCase

from occult import write_metrics_file, _read_config, CONF_PROFILE, CONF_ARGS, CONF_TOKEN, CONF_VAULT_ADDR, CONF_VAULT_PATH

import os


class Test(TestCase):
    def test_write_metrics_file(self):
        file_name = "/tmp/occult-metrics.prom"
        try:
            os.remove(file_name)
        except:
            pass
        self.assertFalse(os.path.exists(file_name))
        write_metrics_file(file_name, 60, True)
        self.assertTrue(os.path.exists(file_name))

    def test__read_config(self):
        config_file = "contrib/test.json"
        conf = _read_config(config_file)
        for keyword in CONF_PROFILE, CONF_ARGS, CONF_TOKEN, CONF_VAULT_ADDR, CONF_VAULT_PATH:
            self.assertTrue(keyword in conf)
