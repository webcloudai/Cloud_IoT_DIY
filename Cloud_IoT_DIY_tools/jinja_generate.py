'''
© 2023 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
import sys
from pathlib import Path
from jinja2.nativetypes import NativeEnvironment
from jinja2 import Undefined
# Setup logging.
import logging
logging.basicConfig(level=logging.DEBUG)
# logging.basicConfig(level=aegis_config['log_level'])
_top_logger = logging.getLogger(__name__)
if not _top_logger.hasHandlers():
    _top_logger.addHandler(logging.StreamHandler())
#--- we'll add path to PATH to enable import of common_project_config
sys.path.append("../Cloud_IoT_DIY_cloud")
from common_project_config import ProjectConfig

class PreserveUndefined(Undefined):
    ''' Custom Undefined handler preserving undefined jinja variables '''
    # inspired by jinja2.DebugUndefined implementation
    def __str__(self) -> str:
        if self._undefined_name:
            message = f"{self._undefined_name}"
        else:
            message = f"jinja error"
        return f"{{{{ {message} }}}}"

if __name__=="__main__":    
    #################################################################################
    # Collect Project Configuration
    pr_config = ProjectConfig.create_from_file()
    jjenv = NativeEnvironment(undefined=PreserveUndefined)

    folders_to_handle = [
        Path(pr_config.firmware_folder) / "src", Path(pr_config.firmware_folder) / "lib",
        Path(pr_config.web_site_location) / "lib"
    ]
    for fold_path in folders_to_handle:
        for j_templ in fold_path.rglob("*.jinja"):
            _top_logger.info(f"Will generate file {j_templ.stem} with template {j_templ.name}")
            with open(j_templ, "r") as f:
                templ = f.read()
            generated = jjenv.from_string(templ).render({
                **pr_config.config_data,
                **{}
            })
            # we'll run it second time to support in template replacements
            generated = jjenv.from_string(generated).render({
                **pr_config.config_data,
                **{}
            })
            with open(j_templ.with_suffix(""), "w") as f:
                f.write(generated)