# Use an existing docker image as a base
FROM python:3.9.7-buster

# create a new folder in your container for your application
WORKDIR /usr/app/server
# copy requirements.txt to the working directory of the container 
COPY ./requirements.txt ./
# Download and install dependencies
RUN pip install -r requirements.txt
RUN apt-get update
RUN apt-get install ffmpeg libsm6 libxext6  -y

COPY ./ ./
# Tell the image what to do when it starts as a container
CMD ["python3", "server.py"]