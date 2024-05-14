sudo python3 clearCores.py

cd ~/DeathStarBench/socialNetwork
sudo docker-compose down
sudo docker volume rm $(sudo docker volume ls -q)
sudo docker-compose up -d

cd ~/parties3/manager
