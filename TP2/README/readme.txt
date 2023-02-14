Para iniciar o serviço de streaming, será necessário correr três programas diferentes, sendo eles o server, oNode e o client.
Primeiramente, deverá ser executado o programa server em todos os servidores da topologia, passando como argumentos o caminho para o ficheiro json que contém a configuração de toda a topologia e o segundo é um caracter numérico 1 ou 0, o 1 é usado para exprimir que esse servidor será o principal (bootstraper), servindo para conectar todos os nodos, e 0 será usada para os restantes servidores.
Seguidamente será executado o oNode em todos o routers pertencentes à rede overlay, este programa terá um único argumento, sendo ele o IP do bootstraper.
Por fim, quando um cliente realiza um pedido de stream, este deve executar o client, passando 2 argumentos, o primeiro é o IP do nodo vizinho, pertencente à rede overlay, e o ultimo o nome do ficheiro de vídeo que pretende receber.

Exemplo:
python3 server.py topologias/topo.json 1
python3 oNode.py 10.0.0.10
python3 client.py 10.0.20.1 movie.Mjpeg
