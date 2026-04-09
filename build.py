#!/usr/bin/python3

# external modules
import jsonschema

# builtin modules
import argparse
import logging
import os
import glob
import shutil
import pprint
import sys
import subprocess
import re
import json
import base64
import urllib


def print_section(name: str) -> None:
    """Display section name"""
    DEBUG_LINE = '#'*40
    print('')
    print(DEBUG_LINE)
    print(f'# {name}')
    print(DEBUG_LINE)


def check_docker_version() -> None:
    """Check if the version of Docker is not too high (>= 25)"""
    logger = logging.getLogger()

    result = subprocess.run(['docker', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    version_output = result.stdout.strip()
    logger.debug(version_output)
    pattern = r"Docker version (\d+\.\d+\.\d+),"
    matches = re.findall(pattern, version_output)
    if not len(matches):
        logger.critical('Could not find Docker version')
        sys.exit(1)
    docker_version = matches[0].split('.')[0] # 20.21.22 -> 20
    maximum_docker_version = 25
    if int(docker_version) >= maximum_docker_version:
        logger.info(f'Docker version {docker_version} is too high. Siemens allows maximum version: {maximum_docker_version}')
        sys.exit(1)
    logger.info(f'Docker version {docker_version}<={maximum_docker_version} is ok')


def check_dependencies(dependencies_name: str) -> None:
    """Check if the specified dependencies is installed in the system"""
    logger = logging.getLogger()

    path = shutil.which(dependencies_name)
    if path:
        logger.info(f'`{dependencies_name}` is installed')
    else:
        logger.critical(f'`{dependencies_name}` does not seem to be present in the system')
        sys.exit(1)
    
    if dependencies_name == 'docker':
        check_docker_version()


def check_target_dir(target_path: str) -> dict:
    """
    Check if the files for the app is present.
    Files needed include:   - *_json_ui.json
                            - OpenReconSchema_*.json
                            - *.py (process file)
    Return a dict with the name of files of interest
    """
    logger = logging.getLogger()

    # files to find
    json_ui_pattern = '*_json_ui.json'
    schema_pattern  = 'OpenReconSchema_*.json'
    json_ui_list = glob.glob(os.path.join(target_path, json_ui_pattern))
    schema_list  = glob.glob(os.path.join(target_path, schema_pattern ))

    if len(json_ui_list) == 1:
        logger.info(f'Found JSON UI file : {json_ui_list[0]}')
    else:
        logger.error(f'Found {len(json_ui_list)}/1 JSON UI file with pattern {json_ui_pattern} in {target_path}')
        sys.exit(1)

    if len(schema_list) == 1:
        logger.info(f'Found OpenReconSchema file : {schema_list[0]}')
    else:
        logger.error(f'Found {len(schema_list)}/1 OpenReconSchema file with pattern {schema_pattern} in {target_path}')
        sys.exit(1)

    process_name = os.path.splitext( os.path.basename(json_ui_list[0]) )[0].replace('_json_ui', '')
    schema_name  = os.path.splitext( os.path.basename( schema_list[0]) )[0]

    # fetch the .py process
    process_path = os.path.join(target_path, f'{process_name}.py')
    if os.path.exists(process_path):
        logger.info(f'Found .py process file : {process_path}')
       
    else:
        logger.error(f'.py process not found : {process_path}')
        sys.exit(1)

    target_data = {
        'name' : {
            'process': process_name,
            'schema' :  schema_name,
        },
        'path': {
            'process' : process_path,
            'ui_json' : json_ui_list[0],
            'schema'  :  schema_list[0],
        }
    }
    pprint.pprint(target_data, sort_dicts=False)

    return target_data


def build_server(dockerfile_path: str) -> None:
    """Build the server image"""
    logger = logging.getLogger()

    # build docker image for python-openrecon-server
    # this image is the starting point, that will be refined latter
    logger.info('building docker image `python-openrecon-server`')
    subprocess.run(['docker', 'build', '--tag', 'python-openrecon-server', '--file', dockerfile_path, './'], check=True)


def check_json_format(json_content, target_data: dict) -> bool:
    """Compare json content to the json schema reference"""
    logger = logging.getLogger()

    logger.info(f"load JSON Schema : {target_data['path']['schema']}")
    with open(file=target_data['path']['schema'], mode='r') as fid:
        schema_content = json.load(fp=fid)

    validator = jsonschema.Draft7Validator(schema=schema_content)

    errors = list(validator.iter_errors(instance=json_content))
    if errors:
        logger.error('our Json vs. Schema errors :')
        for error in errors:
                logger.error(error)
        return False
    
    logger.info(f'No error in out JSON compared against the Schema')
    return True


def write_dockerfile(cmdline: str, json_content, build_data: dict) -> None:
    """Write the content of the Dockerfile"""
    logger = logging.getLogger()

    # encoded the json content in base 64
    encoded_json_content = base64.b64encode((json.dumps(obj=json_content,indent=2)).encode('utf-8')).decode('utf-8')

    # write the Dockerfile content
    logger.info(f"Write `build` Dockerfile : {build_data['path']['docker']}")
    dockerfile_content = [
        f'# import python-openrecon-server as starting point',
        f'FROM python-openrecon-server AS base',
        f'',
        f'ENV NVIDIA_VISIBLE_DEVICES=all NVIDIA_DRIVER_CAPABILITIES=compute,utility',
        f'',
        f'# CMD line',
        f'{cmdline}',
        f'',
        f'# mandatory for OpenRecon (see OR documentation)',
        f'LABEL "com.siemens-healthineers.magneticresonance.openrecon.metadata:1.1.0"="{encoded_json_content}"',
        f'',
    ]
    dockerfile_content = "\n".join(dockerfile_content)
    with open(file=build_data['path']['docker'], mode='w') as fid:
        fid.writelines(dockerfile_content)


def create_pdf(file_path: str, lines_of_text: list[str]) -> None:
    """Generate a pdf with informations about the app"""
    pdf_header = b'%PDF-1.4\n'
    
    objects = []
    objects.append(b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n') # Object 1: Catalog
    objects.append(b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n') # Object 2: Pages
    objects.append(b'3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n') # Object 3: Page
    
    # Object 4: Page content
    content_stream = "BT /F1 24 Tf 100 750 Td" 
    for line in lines_of_text:
        content_stream += f" ({line}) Tj 0 -30 Td"
    content_stream += " ET"
    objects.append(f'4 0 obj\n<< /Length {len(content_stream)} >>\nstream\n{content_stream}\nendstream\nendobj\n'.encode())
    objects.append(b'5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n') # Object 5: Font
    
    pdf_body = b''.join(objects)
    
    # Cross-reference table
    xref_offset = len(pdf_header)
    xref = b'xref\n0 6\n0000000000 65535 f \n'
    xref_entry_offsets = [xref_offset]
    for obj in objects:
        xref_entry_offsets.append(xref_entry_offsets[-1] + len(obj))
    for offset in xref_entry_offsets:
        xref += f'{offset:010} 00000 n \n'.encode()
    
    trailer = f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_entry_offsets[-1]}\n%%EOF'.encode()
    
    # Write
    with open(file_path, 'wb') as f:
        f.write(pdf_header)
        f.write(pdf_body)
        f.write(xref)
        f.write(trailer)


def packaging_OR_image(build_data: dict, info: dict) -> None:
    """
    Packaging an OpenRecon image into a single .zip file
    containing the Docker image (.tar), created using docker save,
    and its documentation('.pdf')
    """
    logger = logging.getLogger()

    cwd = os.getcwd()
    build_path = os.path.join(cwd, 'build')

    # save docker image in a .tar
    logger.info(f"(1/2) saving image `{build_data['name']['docker']}` in a .tar {build_data['path']['tar']}")
    subprocess.run(['docker', 'save', '-o', build_data['path']['tar'], build_data['name']['docker']], check=True)
    logger.info(f"(2/2) saving image DONE")

    # generate PDF
    lines = [
        f'vendor={info['vendor']}',
        f'name={info['name']}',
        f'version={info['version']}',
    ]
    logger.info(f"write PDF file : {build_data['path']['pdf']}")
    create_pdf(file_path=build_data['path']['pdf'], lines_of_text=lines)

    # save everything in a ZIP file
    logger.info(f"(1/2) zip all files : {build_data['path']['zip']}")
    subprocess.run(['zip', build_data['name']['base']+'.zip', build_data['name']['base']+'.tar', build_data['name']['base']+'.pdf'], check=True, cwd=build_path)
    logger.info(f"(2/2) zip all files DONE")


def generate_names(build_path: str, extension: str, json_content) -> str:
    """Generate the name of the file according to OpenRecon standards"""
    logger = logging.getLogger()

    version = json_content['general']['version']
    vendor  = json_content['general']['vendor' ]
    name    = json_content['general']['id'     ]

    if (extension not in ("Dockerfile", "zip", "tar", "pdf")):
        logger.info("Unexpedted extension provided")

    file_name = os.path.join(build_path, f"OpenRecon_{vendor}_{name}_V{version}.{extension}")
    return file_name


def prepare_infos(json_content, build_path: str, target_data: dict) -> dict:
    """Generate the names of the building files(Dockerfile, .tar, .zip)"""
    logger = logging.getLogger()

    # prep build dir
    if os.path.exists(build_path):
        logger.info(f'`build` dir found : {build_path}')
    else:
        os.mkdir(build_path)
        logger.info(f'`build` dir created : {build_path}')

    # prep info
    if args.debug:
        cmdline  = f'CMD [ "/bin/bash", "-c", "/usr/sbin/ldconfig && exec python3 main.py --debug -H=0.0.0.0 -p=9002 -l=/tmp/python-openrecon-server.log --config={target_data['name']['process']}"]'
    else:
        cmdline  = f'CMD [ "/bin/bash", "-c", "/usr/sbin/ldconfig && exec python3 main.py -H=0.0.0.0 -p=9002 -l=/tmp/python-openrecon-server.log --config={target_data['name']['process']}"]'
    
    version = json_content['general']['version']
    vendor  = json_content['general']['vendor' ]
    name    = json_content['general']['id'     ]

    # other file/path
    base_name = f'OpenRecon_{vendor}_{name}_V{version}'

    build_data = {
        'cmdline': cmdline,
        'info': {
            'version'   : version,
            'vendor'    : vendor,
            'name'      : name
        },
        'name': {
            'docker': f'OpenRecon_{vendor}_{name}:V{version}'.lower(),
            'base'  : f'OpenRecon_{vendor}_{name}_V{version}'
        },
        'path': {
            'docker' : os.path.join(build_path, f"{base_name}.Dockerfile"),
            'tar'   : os.path.join(build_path, f"{base_name}.tar"),
            'pdf'   : os.path.join(build_path, f"{base_name}.pdf"),
            'zip'   : os.path.join(build_path, f"{base_name}.zip")
        }
    }

    pprint.pprint(build_data, sort_dicts=False)

    return build_data


def main(args: argparse.Namespace):

    #############
    ### setup ###
    #############

    logger = logging.getLogger()

    print_section('START')
    logger.info(f'Start of {os.path.basename(__file__)}')
    logger.warning('Untill the BUILD part, there is a "skip if already done" feature')
    cwd = os.getcwd()
    logger.info(f'Current working directory : {cwd}')


    # check if all system programs are here
    print_section('SYSTEM DEPENDENCIES')
    check_dependencies('zip')
    check_dependencies('git')
    check_dependencies('docker')

    # check if the necessary file are present in the target dir
    target_path = os.path.join(cwd, args.dirname)
    print_section(f'Check `target` dir and its content : {target_path}')
    target_data = check_target_dir(target_path)


    #############
    ### build ###
    #############

    # Build docker image of the server
    print_section('BUILD SERVER')
    cwd = os.getcwd()
    dockerfile_path = os.path.join(cwd, 'Dockerfile')
    build_server(dockerfile_path)

    print_section('BUILD')
    logger.warning('From now on, all steps will not have a "skip if already done" feature')

    # prep build dir
    build_path = os.path.join(cwd, 'build')

    # load JSON UI
    logger.info(f"load UI JSON content : {target_data['path']['ui_json']}")
    with open(target_data['path']['ui_json'], 'r') as fid:
        json_content = json.load(fid)
    
    # Check if our updated JSON is ok
    if not check_json_format(json_content, target_data):
        sys.exit(1)

    build_data = prepare_infos(json_content, build_path, target_data)

    # Write the Dockerfile
    write_dockerfile(build_data['cmdline'], json_content, build_data)

     # build docker image
    logger.info(f"building docker image `{build_data['name']['docker']}` from Docker file {build_data['path']['docker']}")
    subprocess.run(['docker', 'build', '--tag', build_data['name']['docker'], '--file', build_data['path']['docker'], cwd], check=True)

    # generate a pdf documentation and save the docker image and its doc in a .zip
    if not args.nopackage : 
        packaging_OR_image(build_data, build_data['info'])

    # END
    print_section('All done !')
    sys.exit(0)


if __name__ == '__main__':

     # setup logging
    logging.basicConfig(
        level=logging.DEBUG,
        format=f"%(levelname)8s:%(funcName)15s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        prog            = 'build',
        description     = 'Build OpenRecon app',
        formatter_class = argparse.ArgumentDefaultsHelpFormatter,
    )

    def dir_path(input_dir):
        if os.path.isdir(input_dir):
            return input_dir
        else:
            raise argparse.ArgumentTypeError(f"Not a valid path : {input_dir}")

    parser.add_argument(
        '--dirname',
        type    = dir_path,
        help    = 'Application directory name. ex: `demo-i2i`, `app`',
        default = 'app'
    )
    parser.add_argument('-d', '--debug', action='store_true', help='Build the server in debug mode')
    parser.add_argument('--nopackage', action='store_true', help='Do not save the docker image in a .zip file')

    args = parser.parse_args()

    main(args)
