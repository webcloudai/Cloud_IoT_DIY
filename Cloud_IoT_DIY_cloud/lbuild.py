'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
# helper script to build and prepare deployment for AWS Lambda when pip is used as a package manager
# NOTE: it's expected that:
# - every lambda function is located in the dedicated subfolder of src folder named exactly as Lambda function
# - requirements for all lambdas are available in lambda_requirements.txt file
#   (this may be improved with different requirements per lambda)
#
# This script is somewhat analog of this set of commands executed for every lambda
'''
rm -R build_lambda
mkdir build_lambda
rm -R deploy_lambda
mkdir deploy_lambda
cp src/* build_lambda
pip install --target ./build_lambda -r requirements.txt
cd build_lambda
zip -r ../deploy_lambda/deployment-package.zip . 
'''
import sys
import subprocess
import shutil
from pathlib import Path
import argparse
#-------------------------
import logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stderr, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
_top_logger = logging.getLogger(__name__)
if not _top_logger.hasHandlers():
        _top_logger.addHandler(logging.StreamHandler(stream=sys.stderr))



dependencies_list:Path = Path("lambda_requirements.txt")

# NOTE: Current implementation do not preserve previous builds and deployments!
# create build version from datetime (if needed) - NOT SUPPORTED FOR NOW
# create current build subfolder - NOT SUPPORTED FOR NOW

def parse_arguments():
    ''' this is required ONLY if command line is used '''
    parser = argparse.ArgumentParser(
        description="Build all Lambda Functions and (optionally) run 'cdk synth' and 'cdk deploy'",
        usage=''' python3 lbuild.py --synth {'--verbose'}'''
    )
    parser.add_argument("--synth", "-s", dest="cdk_synth_parameters", default="", required=False, help="Run build and cdk synth with options provided in this parameter")
    parser.add_argument("--deploy", "-dp", dest="cdk_deploy_parameters", default="", required=False, help="Run build, pre-deployment and cdk deploy with options provided in this parameter")    
    parser.add_argument("--destroy", "-ds", dest="cdk_destroy_parameters", default="", required=False, help="Run cdk destroy with options provided in this parameter and post-destroy")    
    parser.add_argument("--sources_folder", "-sf", dest="sources_folder", required=False, default="./src", help="Path of the folder with Lambda sources subfolders")
    parser.add_argument("--build_folder", "-bf", dest="build_folder", required=False, default="./build_lambda", help="Path of the temp folder where Lambda build process happens")
    parser.add_argument("--deploy_folder", "-df", dest="deployment_folder", required=False, default="./deploy_lambda", help="Path of the folder with Lambda deployment packages")
    parser.add_argument("--deployment_package", "-dn", dest="deployment_package", required=False, default="lambda-deployment-package", help="common suffix for all Lambda deployment packages")

    args = parser.parse_args()
    return args



if __name__=="__main__":

    # parse and collect command line arguments
    my_args = parse_arguments()
    _top_logger.debug(my_args)

    run_deploy = my_args.cdk_deploy_parameters.replace("{","").replace("}","")
    run_synth = my_args.cdk_synth_parameters.replace("{","").replace("}","")
    run_destroy = my_args.cdk_destroy_parameters.replace("{","").replace("}","")
    master_sources_folder:Path = Path(my_args.sources_folder)
    build_folder:Path = Path(my_args.build_folder)
    deploy_folder:Path = Path(my_args.deployment_folder)
    deployment_package_name:Path = Path(my_args.deployment_package)

    # create build folder if needed
    # create deploy folder if needed
    for check_folder in [build_folder, deploy_folder]:
        if check_folder.is_file():
            raise RuntimeError(f"File named {check_folder} exists. Please rename or remove it!")

        if check_folder.is_dir():
            # folder exists - cleanup maybe required
            shutil.rmtree(check_folder)

        # we'll create deploy_folder as build folder will be created by copytree
        if check_folder==deploy_folder:
            Path(check_folder).mkdir(parents=True, exist_ok=True)

    # build and pack for deployment all lambda functions
    for sources_folder in master_sources_folder.glob("*"):
        if not sources_folder.is_dir():
            # we skip all files in the src folder as
            # every lambda MUST be in the dedicated SUBFOLDER
            continue
        lambda_name = sources_folder.parts[-1]
        _top_logger.info(f"Will build/package {lambda_name}")

        work_folder = build_folder
        # check if we're building Lambda Layer (folders structure inside zip must be different!)
        # see https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html
        if lambda_name.startswith("_"):
            work_folder = build_folder / "python" / lambda_name

        # copy sources to build subfolder
        shutil.copytree(sources_folder, work_folder)
        # install dependencies to build subfolder
        # *NOTE* if lambda subfolder will have requirements.txt it'll be used instead of global lambda_requirements.txt
        # *NOTE* you can put empty requirements.txt into function folder if it doesn't have any dependencies
        # it's not recommended to use ._main for pip
        # see https://pip.pypa.io/en/latest/user_guide/#using-pip-from-your-program
        one_lambda_dependencies = sources_folder / "requirements.txt"
        if not one_lambda_dependencies.is_file():
            one_lambda_dependencies = dependencies_list
        if one_lambda_dependencies.is_file() and one_lambda_dependencies.stat().st_size>0:
            command_line = [sys.executable, "-m", "pip", "install", "--target", str(work_folder), "-r", str(one_lambda_dependencies)]
            # *NOTE* blocking check_call is used as process is typically fast running
            subprocess.check_call(command_line)
            

        # zip build to deploy folder with name according to current build (if needed)
        shutil.make_archive(
            str(deploy_folder / f"{lambda_name}_{deployment_package_name}"),
            format="zip",
            root_dir=build_folder,
            verbose=True
        )

        # clean up build folder (just delete whole folder)
        shutil.rmtree(build_folder)
        # build folder will be created automatically by copytree

    # check if we were asked to run cdk synth
    if isinstance(run_synth, str) and len(run_synth)>0:
        command = f"cdk synth {run_synth}"
        _top_logger.info(f"Will execute '{command}'")
        try:
            run_process = subprocess.check_call(command, shell=True)
        except ChildProcessError:
            _top_logger.error(f"'{command}' execution was unsuccessful")
            exit(-1)
        except Exception as e:
            _top_logger.error(f"'{command}' execution failed with exception {e}")
    
    # check if we were asked to run cdk deploy
    if isinstance(run_deploy, str) and len(run_deploy)>0:
        commands = [
            (f"source .infra_venv/bin/activate; python pre_deploy.py --deploy", f"Will run pre-deploy"),
            (f"cdk deploy {run_deploy}", f"Will execute 'cdk deploy'")
        ]
        for (command, message) in commands:
            try:
                _top_logger.info(message)
                run_process = subprocess.check_call(command, shell=True)
            except ChildProcessError:
                _top_logger.error(f"'{command}' execution was unsuccessful")
                exit(-1)
            except Exception as e:
                _top_logger.error(f"'{command}' execution failed with exception {e}")

    # check if we were asked to run cdk destroy
    if isinstance(run_destroy, str) and len(run_destroy)>0:
        commands =[
            (f"cdk destroy {run_destroy}", f"Will execute"),
            (f"source .infra_venv/bin/activate; python pre_deploy.py --destroy", f"Will run post-destroy")
        ]
        for (command, message) in commands:
            try:
                _top_logger.info(f"{message} '{command}'")
                run_process = subprocess.check_call(command, shell=True)
            except ChildProcessError:
                _top_logger.error(f"'{command}' execution was unsuccessful")
                exit(-1)
            except Exception as e:
                _top_logger.error(f"'{command}' execution failed with exception {e}")
