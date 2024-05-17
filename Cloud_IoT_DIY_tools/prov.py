'''
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License
'''
# from __future__ import annotations
from typing import Dict, Callable
import PySimpleGUI as sg
import json
import logging
import sys
import asyncio

# Setup logging.
logging.basicConfig(level=logging.DEBUG)
# logging.basicConfig(level=aegis_config['log_level'])
_top_logger = logging.getLogger(__name__)
if not _top_logger.hasHandlers():
    _top_logger.addHandler(logging.StreamHandler())


#--- Proprietary modules
from cloud_client import AwsCloudClient, CloudClient
from process_ui.data_model import CommandToExecute, StepState
from process_ui.process_navigator import ProcessNavigator
from thing_prov.project_navigator import AppProcessNavigator
from thing_prov.project_data_model import AppDataModel

##############################################################
# General Principle
#
# Step enum defines names for every step and substeps
# Child of ProcessNavigator defines what steps are required and in what order
# Child of StepController defines what each step is doing
#
# ProcessNavigator:
# - returns tab group - list of tabs (steps) required to complete the Process
# - handle cloud connection for all tabs (if needed)
# - aggregate delegates from underlying StepControllers
#
# StepController returns it's tab only! 
# But also in charge of delegates - dict with {event name: callable} to handle events
# 
#
# Scenario 1 (simple):
# Each StepController defines ONE action
#
# Scenario 2 (complicated):
# Step consists of substeps - in this case
# - Step has property _subprocess defined as another Child of ProcessNavigator
# - no definition of tab required - it'll be handled by base StepController with the help of ProcessNavigator

# Global window refresh blocked when some delegate us executing
# main_window:sg.Window = None
# app_navigator:AppProcessNavigator = None
# app_delegates:Dict[str, Callable] = None
def update_main_window():
    ''' '''
    # do nothing
    return
    global app_navigator, main_window, app_delegates
    app_navigator.current_window = rerender_window(main_window, app_navigator)
    app_delegates = app_navigator.delegates()


def rerender_window(current_window:sg.Window, application:ProcessNavigator)->sg.Window:
    current_window.close()
    app_layout = [[ application.tab_group() ]]
    sg.theme('GreenTan')
    w = sg.Window('Thing provisioning', app_layout, finalize=True)
    add_enter_event(w)
    return w

def add_enter_event(w:sg.Window):
    for elem in w.element_list():
        if isinstance(elem, sg.InputText):
            elem.bind("<Return>", "")

if __name__=="__main__":
    cclient = AwsCloudClient()
    app_data_model = AppDataModel(cloud_client=cclient)
    app_navigator = AppProcessNavigator(data=app_data_model)
    app_navigator.refresh_main_window_callback = update_main_window
    # collect navigator delegates (event handlers)
    app_delegates = app_navigator.delegates()
    # collect navigator layout (main window layout)
    app_layout = [[ app_navigator.tab_group() ]]
    #
    main_window = sg.Window('Thing provisioning', app_layout, finalize=True)
    app_navigator.current_window = main_window
    # add <Enter> event for any InputText (if any)
    add_enter_event(main_window)
    current_window = main_window
    command_is_executed:bool = False
    # main loop
    while True:
        # 1. Read from background command execution STDOUT queue (if any)
        # *NOTE* we are not using command_is_executed due to async nature (command_is_executed may be false but messages still coming)
        if app_navigator.command_output_queue:
            try:  
                line = app_navigator.command_output_queue.get_nowait()
            except Exception as e:
                # no stdout line available
                pass
            else: 
                # got line
                line = line.decode(errors='replace' if (sys.version_info) < (3, 5) else 'backslashreplace').rstrip()
                # store line of STDOUT in dedicated property
                app_navigator.process_output.append(line)
                current_window[app_navigator.stdout_key].update(f"{line}\n", append=True, autoscroll=True)
                # print(line)
                app_navigator._service_window.Refresh() if app_navigator._service_window else None        # yes, a 1-line if, so shoot me

        # 2. Read from background command execution STDERR queue (if any)
        if app_navigator.command_errors_queue:
            try:  
                line = app_navigator.command_errors_queue.get_nowait()
            except Exception as e:
                # no stderr line available
                pass
            else: 
                # got line
                line = line.decode(errors='replace' if (sys.version_info) < (3, 5) else 'backslashreplace').rstrip()
                # store line of STDERR in dedicated property
                app_navigator.process_errors.append(line)
                current_window[app_navigator.stderr_key].update(f"{line}\n", append=True, autoscroll=True)
                # print(line, file=sys.stderr)
                app_navigator._service_window.Refresh() if app_navigator._service_window else None        # yes, a 1-line if, so shoot me

        # 3. Check if command execution completed - we control command_thread which relies on subprocess STDOUT
        if command_is_executed and (app_navigator.command_process and not app_navigator.command_thread.is_alive()):
            # command execution completed - update buttons (we may have multiple "Close" buttons all disabled by default)
            close_bttn_updated = [
                elem.update(disabled=False, text=elem.ButtonText+" - Now you can PRESS to close operations window")
                for elem in current_window.element_list() if isinstance(elem, sg.Button) and elem.key.startswith("Close")]
            # refresh service window
            app_navigator._service_window.Refresh() if app_navigator._service_window else None        # yes, a 1-line if, so shoot me
            # mark that command execution completed
            command_is_executed = False                

        # 4. Check for background_process_completion_queue
        if app_navigator.background_process_completion_queue:
            try:  
                log_line = app_navigator.background_process_completion_queue.get_nowait()
            except Exception as e:
                # no stdout line available
                pass
            else: 
                
                main_window = rerender_window(main_window, res)
                app_delegates = app_navigator.delegates()
                current_window = main_window
                app_navigator.current_window = main_window
        # 4. Check of logs available in logs queue
        # if app_navigator.logs_queue and app_navigator.logs_element_name:
        #     try:  
        #         log_line = app_navigator.logs_queue.get_nowait()
        #     except Exception as e:
        #         # no stdout line available
        #         pass
        #     else: 
        #         # got line
        #         current_window[app_navigator.logs_element_name].update(f"{log_line}\n", append=False, autoscroll=True)
        #         # print(log_line)
        #         main_window = rerender_window(main_window, res)
        #         app_delegates = app_navigator.delegates()
        #         current_window = main_window
        #         app_navigator.current_window = main_window

        # 10. Check events from all windows
        event_window, event, values = sg.read_all_windows(timeout=10)
        if event==sg.TIMEOUT_EVENT:
            # that's Ok -  no events found
            # we just need non-blocking method
            continue
        _top_logger.debug(f"\nevent: {event}\nvalues:\n{json.dumps(values, indent=3)}")

        # 10.1. Always check if main window closed first
        if current_window==main_window and event == sg.WIN_CLOSED:           # always,  always give a way out!
            break
        # 10.2. Service window logic
        if current_window!=main_window:
            if event in [app_navigator.command_failure_key, app_navigator.command_success_key]:
                # 3.2.1. Close Service Window
                app_navigator.close_service_window()
                # 3.2.2. Invoke delegate (method from StepController started the command)
                res = app_navigator.command.delegate(
                    **{**values, **{"state":StepState.EXECUTIONSUCCES if event==app_navigator.command_success_key else StepState.EXECUTIONFAILED}})
                # 3.2.3. Rerender main windows depending from delegate response
                if isinstance(res, ProcessNavigator):
                    main_window = rerender_window(main_window, res)
                    app_delegates = app_navigator.delegates()
                # 3.2.4. Finally mark main window as current
                current_window = main_window
                app_navigator.current_window = main_window            
            elif event == "Terminate operation subprocess":
                app_navigator.cancel_command()
        # 10.3. Main window logic
        elif event in app_delegates:
            # we'll invoke delegate and act by result
            event_handler:Callable[[Dict], ProcessNavigator] = app_delegates[event]
            res:ProcessNavigator = event_handler({**values,**{"__event_name":event}})
            if isinstance(res, ProcessNavigator):
                # we need to rerender the main_window (update main_window layout)
                main_window = rerender_window(main_window, res)
                app_delegates = app_navigator.delegates()
                current_window = main_window
                app_navigator.current_window = main_window
            elif isinstance(res, CommandToExecute):
                # we'll switch to service window and run execution
                command_is_executed = True
                app_navigator.command = res
                # rerender main window (probably block some interactions)
                main_window = rerender_window(main_window, app_navigator)
                app_delegates = app_navigator.delegates()
                # change current window
                current_window = app_navigator.service_window()
                app_navigator.current_window = current_window
                # start command execution
                app_navigator.execute_command(res)
            else:                    
                _top_logger.debug(f"Unexpected delegate return: {res}")

    # Clean up
    try:
        asyncio.gather(app_navigator.thingcomm_client.disconnect())
    except Exception as e:
        _top_logger.warning(f"FAIL to close the connection with exception {e}")
    main_window.close()
    if app_navigator and app_navigator._service_window:
        app_navigator._service_window.close()

exit(0)
