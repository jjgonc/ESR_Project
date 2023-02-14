import socket
import pickle
import sys
import database
from threading import Thread
import time
from time import sleep
import re
import netifaces
import ServerWorker

# obter as interfaces do oNode
def getMyNames():
        mynames = []
        index = 0
        for interface in netifaces.interfaces():
                if(index != 0):
                        for link in netifaces.ifaddresses(interface)[netifaces.AF_INET]:
                                    mynames.append(link['addr'])
                index = index + 1
        return mynames


# obter a stream a partir das melhores metricas
def getStream(database,filename,comeFrom,server):

        print('getting stream',flush=True)

        bestNeighbour = ''

        # obter o melhor vizinho conforme seja um servidor ou um cliente
        if server == True:
                bestNeighbour = database.getBestMetricsServerStatus(comeFrom)
        else :
                bestNeighbour = database.getBestMetricsRouteStreamDict(filename)


        database.putStreamEmpty(filename)

        #enviar o request para o melhor vizinho (ou caso seja necessário, para o servidor)
        msg = ''
        if server:
                msg       = f'{filename} 1'
        else :
                msg       = f'{filename} 0'
        
        print(bestNeighbour)
        
        # uso de UDP para enviar o request da stream
        udpSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        udpSocket.sendto(msg.encode(), (bestNeighbour,6666))
        
        i = 0
        
        while database.getStreamState(filename) == 'activated':         #enquanto se pretender receber a stream (marcado com activated ou disabled)
                # print(i)
                response,adress = udpSocket.recvfrom(100000)
                i = i + 1
                try:
                        for receiver in database.getStreamReceivers(filename):          #separação para caso de oNodes
                                # print(receiver)
                                udpSocket.sendto(response,receiver)
                        for client in database.getStreamClients(filename):              # separação para caso de clientes
                                # print(client)
                                database.putStreamPacket(filename,client,response)
                except:
                        pass
        
        msg = f'{filename} TEARDOWN'
        udpSocket.sendto(msg.encode(), (bestNeighbour,6666))
        
        
        
# receber um request de stream
def receiveStreamRequest(database):

        udpSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        udpSocket.bind(('', 6666))

        while(True):

                msg , address = udpSocket.recvfrom(100000)

                print(address)

                request = msg.decode()

                splitted = re.split(' ',request)

                filename = splitted[0]
                
                server = splitted[1] #or teardown

                if server != 'TEARDOWN':

                        # perguntar recursivamente até chegar servidor
                        if server == '1':
                                        Thread(target=getStream, args = (database,filename,[address[0]],True)).start()  
                        
                        # perguntar recursivamente até chegar a um vizinho com a stream
                        else:   
                                #verify if the node doesnt have the stream
                                stream = database.getStream(filename)
                                if stream == False:
                                        Thread(target=getStream, args = (database,filename,[],False)).start()  
                                else :
                                        print('já possui depois do get', address)
                

                        vartry = False
                        while vartry == False:
                                vartry = database.addStreamReceiver(filename,address)
                # caso de dar teardown numa stream
                else:
                        database.removeStreamReceiver(filename,address)
                


                

# Verificar a stream na vizinhança e mandar resposta
def verifyStreamInNeighbourHood(database, filename,visited):
        

         #get my names
        mynames = getMyNames()
        #construct visited list with all node names
        newvisited = ""
        index = 0
        if len(visited) != 0:
                for vis in visited:
                        if(index == 0):
                                newvisited = newvisited + vis
                        else:
                                newvisited = newvisited + ',' + vis
                        index = index + 1
                for name in mynames:
                        newvisited = newvisited + ',' + name
                        
        else:
                for name in mynames:
                        if index == 0 :newvisited = newvisited + name
                        else: newvisited = newvisited + ',' + name
                        index = index + 1


        for neighbour in database.getNeighbours():
                if neighbour not in visited:
                        # print('verify', neighbour)
                        # print(neighbour)
                        stream_socket = socket.socket()  # instantiate
                        stream_socket.connect((neighbour, 8888))  # connect to the server
                        message = f'filename:{filename} visited:{newvisited}'
                        sendTime = time.time()
                        stream_socket.send(message.encode())  # send message
                        response = stream_socket.recv(1024).decode()
                        receiveTime = time.time()
                        # print(response)
                        if response != 'NAK':                   # caso tenha uma resposta para a stream envia as metricas e o vizinho
                                        metricsDict = {}
                                        splitted = re.split(' ',response)
                                        for string in splitted:
                                                s = re.split(r':',string)
                                                if s[0] == 'time':
                                                        metricsDict['time'] = float(s[1])
                                                        metricsDict['timestamp'] = time.time() - float(s[1])
                                                if s[0] == 'jumps':
                                                        metricsDict['jumps'] = float(s[1]) + 1
                                       
                                        database.putRouteStreamDict(filename,neighbour,metricsDict)
                               
                        
# receber a verificação da stream e ver como pode fazer chegar a stream
def receiveStreamVerification(database):
        
        verification_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        verification_socket.bind(('', 8888))  
        verification_socket.listen(10)

        while True:
                conn, address = verification_socket.accept()

                data = conn.recv(1024)

                msg = data.decode()
                
                splitted = re.split(' ',msg)

                verificationDict = {}
                
                for string in splitted:
                    s = re.split(r':',string)
                    if s[0] == 'filename':
                        verificationDict['filename'] = s[1]

                    if s[0] == 'visited':
                        visited = re.split(',',s[1])
                        if '' in visited : visited.remove('')
                        verificationDict['visited'] = visited
                
                #verificar se já tem a stream

                stream = database.getStream(verificationDict['filename'])

                if(stream != False):                                    # caso já possua a stream
                        print('já possui verificação', address)
                        message = f'time:{time.time()} jumps:{0}'
                        conn.send(message.encode())
                else:                                                   # caso não possua a stream, verifica recursivamente nos vizinhos
                        verifyStreamInNeighbourHood(database, verificationDict['filename'],verificationDict['visited'])
                        if database.getNumberOfRouteStream(verificationDict['filename']) == 0:
                                message = f'NAK'
                                conn.send(message.encode())
                        else:
                                neighbour = database.getBestMetricsRouteStreamDict(verificationDict['filename'])
                                metrics = database.getMetricsRouteStreamDict(verificationDict['filename'], neighbour)
                                print(metrics["time"])
                                message = f'time:{metrics["time"]} jumps:{metrics["jumps"]}'
                                conn.send(message.encode())

                                        

# Inicializar a conexão com o servidor para obter a lista de vizinhos
def neighboursRequest(host_to_connect,database):

        port_to_connect = 1111
        print('Requesting Neighbours...')
        client_socket = socket.socket()  # instanciar
        client_socket.connect((host_to_connect, port_to_connect))  # conectar com o servidor
        message = "REQ_NEIGHBOURS"                                 # mensagem que pede a lista de vizinhos ao servidor
        client_socket.send(message.encode())                       # enviar a mensagem
    
        data = client_socket.recv(1024)                            # receber a resposta do servidor

        client_socket.close()  # fechar a conexão

        neighboursParsed = []

        serversNeighboursParsed = []

        neighboursUnParsed = pickle.loads(data)         # descodificar a resposta do servidor

        for neighbour in neighboursUnParsed:            # colocar a lista de vizinhos em formato utilizável pelo programa, uma vez que os viznhos que são servidores aparecem no ficheiro json com um 's' à frente
                # separar os vizinhos que são servidores dos que são nodos
                if 's' not in neighbour:
                        neighboursParsed.append(neighbour)
                else:
                        
                        serversNeighboursParsed.append(neighbour.replace('s', ''))


        database.putNeighbours(neighboursParsed)                # guardar a lista de vizinhos que não são servidores
        database.putServersNeighbours(serversNeighboursParsed)  # guardar a lista de vizinhos que são servidores

        print(neighboursParsed)
        print(serversNeighboursParsed)


        Thread(target=receiveStatusServerNetwork, args = (database,)).start()

                
# receber o STATUS
def receiveStatusServerNetwork(database):

        
        status_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        status_socket.bind(('', 4444))  
        status_socket.listen(10)

        while True: 
                conn, address = status_socket.accept()
                # print('received from ',address[0],flush=True)
                data = conn.recv(1024)
                # print(data.decode(),flush=True)

                msg = data.decode()

                splitted = re.split(' ',msg)

                connection = {}
                
                timeserver = 0
                for string in splitted:                 # proceder á analise das métricas
                    s = re.split(r':',string)
                    if s[0] == 'servername':
                        servername = s[1]
                        connection['servername'] = servername
                    if s[0] == 'time':
                        timeserver += float(s[1])
                        timestamp = time.time() - float(s[1])
                        connection['timestamp'] = timestamp
                    if s[0] == 'jumps':
                        jumps = int(s[1])
                        connection['jumps'] = jumps
                    if s[0] == 'visited':
                        visited = re.split(',',s[1])
                        if '' in visited : visited.remove('')
                        connection['visited'] = visited
                
                #get my names
                mynames = getMyNames()

                #construct visited list with all node names
                visited = ""
                index = 0
                if len(connection['visited']) != 0:
                        for vis in connection['visited']:
                                if(index == 0):
                                        visited = visited + vis
                                else:
                                        visited = visited + ',' + vis
                                index = index + 1
                        for name in mynames:
                                visited = visited + ',' + name
                                
                else:
                        for name in mynames:
                                if index == 0 :visited = visited + name
                                else: visited = visited + ',' + name
                                index = index + 1
                                

                database.putConnectionServerStatus(address[0],connection)       # atualizar
                
                message = f'servername:{connection["servername"]} time:{timeserver} jumps:{connection["jumps"] + 1} visited:{visited}'

                for neighbour in database.getNeighbours():                      # envio das métricas para os vizinhos
                        if(neighbour not in connection['visited']):
                                connected = False
                                while connected == False: 
                                    try:
                                        status_socket_send = socket.socket()
                                        status_socket_send.connect((neighbour,4444))
                                        status_socket_send.send(message.encode())
                                        status_socket_send.close()
                                        connected = True
                                    except:
                                        pass
                                        

# obter a informação do cliente e começar o tratamento do pedido através do ServerWorker
def server(database, port):
        try:
                SERVER_PORT = int(port)
                rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                rtspSocket.bind(('', SERVER_PORT))
                rtspSocket.listen(5)    
                # Receber a informação do cliente (address,port) através de uma RTSP/TCP session
                while True:
                    clientInfo = {}
                    clientInfo['rtspSocket'] = rtspSocket.accept()
                    ServerWorker.ServerWorker(clientInfo,database).run()
        
        except:
                print("[Usage: Server.py Server_port]\n")


# Thread que vai receber as conexões dos clientese, por cada uma delas, vai criar uma thread para tratar da comunicação
def clientConnections(database):

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(('', 2555))  
        server_socket.listen(10)        # 10 conexoes no maximo
        
        while True:
                conn, address = server_socket.accept()  # accept new connection
                port = conn.recv(1024).decode()
                print(port, 'from ' + address[0])
                Thread(target=server, args = (database,port)).start()




if __name__ == '__main__':

        database = database.database()          # construtor da database associada ao onode, que vai guardar as informações e métricas do nodo relativamente à sua vizinhança
        bootstrapper = sys.argv[1]              # endereço do bootstrapper que vai permitir conhecer a topologia
        Thread(target=neighboursRequest, args = (bootstrapper,database)).start()
        Thread(target=clientConnections, args = (database,)).start()
        Thread(target=receiveStreamVerification, args = (database,)).start()
        Thread(target=receiveStreamRequest, args = (database,)).start()        
       

        
        
   






    