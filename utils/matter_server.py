# This file contains helper functions for the matter physics server

import subprocess
import copyreg
import zmq
from random import randint
import atexit

import os

# socket setup
context = zmq.Context()

JS_LOCATION = 'utils/matter_server.js'

# keeps a dictionary of the references to the PIDs of the node processes so that we can close them safely
pid_reference_manager = {}

if "stimuli" in os.getcwd():
    # if our working directory in stimuli, we need to make sure to find the location of the node file in the right place
    JS_LOCATION = "../"+JS_LOCATION


class Physics_Server:
    def __init__(self, port=None, y_height=8, socket=None, _process=None) -> None:
        if _process is not None:
            self._process = _process
            # increase reference counter
            try:
                pid_reference_manager[self._process.pid] += 1
            except KeyError:
                # this should not happen, since the initialization of a process should always add the PID to the reference manager
                pid_reference_manager[self._process.pid] = 1
        if socket is None:
            self.socket = self.start_server(port)
        else:
            self.socket = socket
            self._process = _process
        # if the height of the canvas differs, we need to subtract it to flip the y axis. 8 is default
        self.y_height = y_height
        # the process should only be set by the deepcopy function

    def __del__(self):
        """Called when the object is deleted."""
        self.kill_server()

    def __deepcopy__(self, memo):
        """Deep copy of the physics server—we keep the same socket and the same process"""
        return Physics_Server(socket=self.socket, y_height=self.y_height, _process=self._process)

    def start_server(self, port=None):
        """Starts the matter physics server and returns a zeromq connection to it."""
        if port is None:
            port = randint(0, 999999999)
        # TODO if necessary add a fallback to tcp:// for Windows users
        self._process = subprocess.Popen(
            ['node', JS_LOCATION, '--port', str(port)])
        # add reference counter
        assert not self._process.pid in pid_reference_manager, "PID already in use"
        pid_reference_manager[self._process.pid] = 1
        socket = context.socket(zmq.REQ)
        while True:
            try:
                # connect to ipc
                socket.connect('ipc:///tmp/matter_server_{}'.format(port))
                break
            except:
                pass
        return socket

    def kill_server(self, force=False):
        """Kills the matter physics server."""
        if force:
            try:
                del(pid_reference_manager[self._process.pid])
                self._process.kill()
            except:
                pass
        if self._process is not None:
            if pid_reference_manager[self._process.pid] == 1:
                # we're the last user of the node server, let's kill it
                del pid_reference_manager[self._process.pid]
                self._process.kill()
            else:
                # there are more references around, but we're letting this one go
                pid_reference_manager[self._process.pid] -= 1

    def blocks_to_serializable(self, blocks):
        return [self.block_to_serializable(block) for block in blocks]

    def block_to_serializable(self, block):
        """Returns a serializable version of the block."""
        return {
            'x': float(block.x),
            'y': float(self.y_height - 1 - block.y),
            'w': float(block.width),
            'h': float(block.height),
        }

    def keep_alive(self):
        """After pickling etc. the socket and the process can be lost. This function checks if we need to restart the node.js process and regenerate the socket."""
        if self._process is None:
            # we don't have a process, so we need to start one
            try:
                del pid_reference_manager[self._process.pid]
            except:
                pass
            self.socket = self.start_server()
        elif self._process.poll() is not None:
            # the process has died, so we need to start a new one
            try:
                del pid_reference_manager[self._process.pid]
            except:
                pass
            self.socket = self.start_server()
        else:
            # we have a process, but it's still alive, so we don't need to do anything
            pass

    def get_stability(self, blocks):
        """Returns the stability of the given blocks.
        Blocks until the result is known.
        """
        self.keep_alive()
        blocks = self.blocks_to_serializable(blocks)
        self.socket.send_json(blocks)
        # receive result—blocking
        result = self.socket.recv()
        # is either 'false' or 'true'
        result = result == b'true'
        return result


def pickle_physics_server(server):
    """Pickle function for physics server. A new process is started when unpickled."""
    return (Physics_Server, (server.y_height,))


# register custom pickle function for the server
copyreg.pickle(Physics_Server, pickle_physics_server)


@atexit.register
def killallprocesses():
    """Kills all the processes that are still running once we close the file (ie. are done with everything)."""
    for pid in pid_reference_manager:
        os.kill(pid, 9)
