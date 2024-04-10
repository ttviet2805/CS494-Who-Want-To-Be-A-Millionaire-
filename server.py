import socket
import selectors
import json
import protocol
import database
import random

class ServerSocket:
    def __init__(self):
        self.mySel = selectors.DefaultSelector()
        self.numClients = None
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients = []

        # Waiting Room
        self.nickNames = []

        # In game
        self.questions = database.questions
        random.shuffle(self.questions)
        self.currentOrder = 0
        self.numsQuestions = len(self.questions)
        self.curQuestion = -1
    
    def runServer(self, serverIP, port):
        self.server.bind((serverIP, port))
        self.server.listen(0)
        print(f"Listening on {serverIP}:{port}")

        clientSocket, clientAddress = self.server.accept()
        print(f"Accepted connection from {clientAddress[0]}:{clientAddress[1]}")

        while True:
            request = clientSocket.recv(1024).decode()

            if self.receiveRequestForClose(clientSocket, request) == True:
                break

            self.receiveRequestForName(clientSocket, request)
            self.receiveRequestForWaitingRoom(clientSocket, request)
            self.receiveRequestForQuestion(clientSocket, request)
            self.receiveRequestForAnswer(clientSocket, request)

        clientSocket.close()
        print("Connection to client closed")
        self.server.close()

    def runServerForNonBlockingSocket(self, serverIP, port):
        self.server.setblocking(False)
        self.server.bind((serverIP, port))
        self.server.listen()
        print(f"Server Listening on {serverIP}:{port}")

        self.mySel.register(self.server, selectors.EVENT_READ, self.accept)

        while self.numClients == None or self.numClients > 0:
            for key, mask in self.mySel.select(timeout=1):
                callback = key.data
                callback(key.fileobj, mask)

        print("Server connection closed")
        self.mySel.close()
        self.server.close()

    def accept(self, sock, mask):
        new_connection, addr = sock.accept()
        if self.numClients == None:
            self.numClients = 1
        else:
            self.numClients += 1
        print('Server Accept({})'.format(addr))
        new_connection.setblocking(False)
        self.mySel.register(new_connection, selectors.EVENT_READ, self.read)
        self.clients.append(new_connection)

    def read(self, clientSocket, mask):
        client_address = clientSocket.getpeername()
        print('Read({})'.format(client_address))
        request = clientSocket.recv(1024).decode()

        if self.receiveRequestForClose(clientSocket, request) == True:
            self.mySel.unregister(clientSocket)
            self.clients.remove(clientSocket)
            clientSocket.close()
            self.numClients -= 1

        self.receiveRequestForName(clientSocket, request)
        self.receiveRequestForWaitingRoom(clientSocket, request)
        self.receiveRequestForQuestion(clientSocket, request)
        self.receiveRequestForAnswer(clientSocket, request)

    def receiveRequestForClose(self, clientSocket, message):
        request = json.loads(message)
        if request.get("type") is None or request.get("protocol") is None:
            return False
        if request.get("protocol") != "REQUEST" or request["type"] != protocol.CLOSE_TYPE:
            return False
        return True

    def receiveRequestForName(self, clientSocket, message):
        request = json.loads(message)
        if request.get("type") is None or request.get("protocol") is None:
            return
        if request.get("protocol") != "REQUEST" or request["type"] != protocol.REG_NICKNAME_TYPE:
            return
        print("Server Received: ", request["data"])
        if self.checkNickName(request["data"]):
            self.nickNames.append(request["data"])
            regCompleteJson = {
                "protocol": "RESPONSE", 
                "type": protocol.REG_NICKNAME_TYPE,
                "data": protocol.REG_COMPLETE_RESPONSE
            }
            clientSocket.send(json.dumps(regCompleteJson, indent=2).encode())
        else:
            regExistJson = {
                "protocol": "RESPONSE", 
                "type": protocol.REG_NICKNAME_TYPE,
                "data": protocol.REG_EXIST_RESPONSE
            }
            clientSocket.send(json.dumps(regExistJson, indent=2).encode())

    def checkNickName(self, curStr):
        if len(curStr) == 0 or len(curStr) > 10:
            return False
        for i in curStr:
            if i.isdigit() or i.isalpha():
                pass
            else:
                return False
        for i in self.nickNames:
            if i == curStr:
                return False
        return True
    
    def receiveRequestForWaitingRoom(self, clientSocket, message):
        request = json.loads(message)
        if request.get("type") is None or request.get("protocol") is None:
            return
        if request.get("protocol") != "REQUEST" or request["type"] != protocol.WAITING_ROOM_TYPE:
            return
        print("Server Received: ", request["data"])
        waitingRoomJson = {
            "protocol": "RESPONSE", 
            "type": protocol.WAITING_ROOM_TYPE,
            "data": self.nickNames
        }
        for client in self.clients:
            client.send(json.dumps(waitingRoomJson, indent=2).encode())
    
    def receiveRequestForQuestion(self, clientSocket, message):
        request = json.loads(message)
        if request.get("type") is None or request.get("protocol") is None:
            return
        if request.get("protocol") != "REQUEST" or request["type"] != protocol.QUESTION_TYPE:
            return
        print("Server Received: ", request["data"])
        self.curQuestion += 1
        questionJson = {
            "protocol": "RESPONSE",
            "type": protocol.QUESTION_TYPE,
            "data": {
                "nickname": request["data"],
                "num_players": len(self.nickNames),
                "current_order": 1,
                "your_order": 1,
                "num_questions": self.numsQuestions,
                "time": 40,
                "current_question": self.curQuestion,
                "question": {
                    "question": self.questions[self.curQuestion]["question"],
                    "answer": self.questions[self.curQuestion]["answer"]
                }
            }
        }
        clientSocket.send(json.dumps(questionJson, indent=2).encode())
    
    def receiveRequestForAnswer(self, clientSocket, message):
        request = json.loads(message)
        if request.get("type") is None or request.get("protocol") is None:
            return
        if request.get("protocol") != "REQUEST" or request["type"] != protocol.ANSWER_TYPE:
            return
        print("Server Received: ", request["data"])
        answerJson = {
            "protocol": "RESPONSE", 
            "type": protocol.ANSWER_TYPE,
            "data": (request["data"]["answer"] == self.questions[self.curQuestion]["correct_answer"])
        }
        clientSocket.send(json.dumps(answerJson, indent=2).encode())


import sys

def main():
    for arg in sys.argv[1:]:
        print("Argument:", arg)
    
    serverIP = "localhost"
    port = 2828
    print(serverIP, port)
    if(len(sys.argv) >= 2):
        serverIP = sys.argv[1]
    if(len(sys.argv) >= 3):
        port = int(sys.argv[2])
    
    serverSocket = ServerSocket()
    serverSocket.runServerForNonBlockingSocket(serverIP, port)

if __name__ == "__main__":
    main()  