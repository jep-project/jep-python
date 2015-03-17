import socket
import time
from jep.protocol import MessageSerializer
from jep.schema import Shutdown

clientsocket = socket.create_connection(('localhost', 9001))
clientsocket.send(MessageSerializer().serialize(Shutdown()))

time.sleep(3)
clientsocket.send(MessageSerializer().serialize(Shutdown()))

time.sleep(3)
clientsocket.shutdown(socket.SHUT_RDWR)
clientsocket.close()
