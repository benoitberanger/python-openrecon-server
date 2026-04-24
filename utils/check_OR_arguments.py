#!/bin/python3

import logging

def check_OR_arguments(configJSON: dict, arg_name: str, arg_type: type, arg_default: any = None) -> any:
    """Return the value of the OpenRecon arguments with the appropriate type"""
    
    if not isinstance(configJSON, dict):
        logging.warning(f"config is not a dictionary. {arg_name} set to {arg_default} by default.")
        return arg_default

    if ('parameters' in configJSON) and (arg_name in configJSON['parameters']):
        logging.info(f"found config['parameters']['{arg_name}'] : type={type(configJSON['parameters'][arg_name])} content={configJSON['parameters'][arg_name]}")
        arg_value =  configJSON['parameters'][arg_name]
    else:
        logging.warning(f"config['parameters']['{arg_name}'] NOT FOUND !! Value set to {arg_default}.")
        return arg_default

    # in OR, the config only provides strings, so need to cast to the correct type
    if arg_type is str:
        pass
    elif arg_type is bool:
        if type(arg_value) is not bool:
            if   arg_value.lower() == 'true' : arg_value = True
            elif arg_value.lower() == 'false': arg_value = False
            else: raise ValueError(f"{arg_name} is detected as `str` but is not 'True' or 'False' ! Cannot cast it to `bool`")
    elif arg_type is int:
        if type(arg_value) is not int:
            arg_value = int(arg_value)
    elif arg_type is float:
        if type(arg_value) is not float:
            arg_value = float(arg_value)
    else:
        raise TypeError('wrong type in the config)')

    logging.info(f'{arg_name} = {arg_value}')
    return arg_value

