#!/bin/python3

import logging

def check_OR_arguments(config, arg_name: str, arg_type: type, arg_default: any) -> any:
    """Return the value of the OpenRecon arguments with the appropriate type"""
    arg_value = arg_default

    if ('parameters' in config) and (arg_name in config['parameters']):
        logging.info(f"found config['parameters']['{arg_name}'] : type={type(config['parameters'][arg_name])} content={config['parameters'][arg_name]}")
        arg_value =  config['parameters'][arg_name]
    else:
        logging.warning(f"config['parameters']['{arg_name}'] NOT FOUND !!")

    # in OR, the config only provides strings, so need to cast to the correct type
    if arg_type is str:
        pass
    elif arg_type is bool:
        if type(arg_value) is not bool:
            if   arg_value == 'True' : arg_value = True
            elif arg_value == 'False': arg_value = False
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



    
    
