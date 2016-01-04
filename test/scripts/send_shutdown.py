import socket
import time
from jep_py.protocol import MessageSerializer
from jep_py.schema import Shutdown

clientsocket = socket.create_connection(('localhost', 9001))

time.sleep(3)
print(clientsocket.recv(10000))

clientsocket.send(MessageSerializer().serialize(Shutdown()))
time.sleep(3)

clientsocket.shutdown(socket.SHUT_RDWR)
clientsocket.close()
