#!/bin/python3

import logging

def check_OR_arguments(configJSON: dict | None, arg_name: str, arg_type: type, arg_default: any = None) -> any:
    """
    Return the value of the OpenRecon arguments with the appropriate type.
    
    In OpenRecon, the config passes all parameter values as strings, 
    regardless of their declared type in the JSON UI definition. This 
    function reads the value from ``configJSON['parameters'][arg_name]`` 
    and casts it to the requested type. If the parameter is missing or 
    the config is invalid, the default value is returned.
    
    Parameters
    ----------
    configJSON : dict or None
        JSON configuration sent by the client. Expected to
        contain a ``'parameters'`` key mapping parameter names to their
        string values. If None or not a dict, arg_default is returned.
    arg_name : str
        Name of the parameter to look up in ``configJSON['parameters']``.
    arg_type : type
        Expected Python type of the parameter. Supported types:
        ``str``, ``bool``, ``int``, ``float``.

    arg_default : any, optional
        Value returned when configJSON is not a dict, when
        ``'parameters'`` is absent, or when arg_name is not found.
        Default is None.

    Returns
    -------
    any
        Parameter value cast to arg_type, or arg_default if not found.
    """
    
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

