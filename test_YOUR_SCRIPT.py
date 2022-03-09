# Paras Savnani

import cv2
import asyncio
import argparse
import pytest
import numpy as np
import multiprocessing as mp
from queue import Queue
from unittest.mock import patch, ANY
from asyncmock import AsyncMock
from asynctest import CoroutineMock
from aiortc import (
    RTCIceCandidate,
    RTCPeerConnection,
    RTCSessionDescription,
    VideoStreamTrack,
)
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder
from aiortc.contrib.signaling import BYE, add_signaling_arguments, create_signaling

from docker_server.server import FrameGenerator
from docker_client.client import ImageProcess, FrameReceiever


@pytest.mark.asyncio
class TestClient:
    """
    Unit test class to test client functionality
    """
    # custom defined centre
    centre = (40,40)

    @pytest.fixture(scope='class')
    def imageProcess(self):
        # Generating dummy queue of frames
        q = mp.Queue()
        
        image = np.zeros((100,100,3), dtype='uint8')
        cv2.circle(image, TestClient.centre, 10, (0,0,255),-1)
        q.put(image)    

        # Generating dummy coordinates
        centre_coordinate = (mp.Value('i', 0), mp.Value('i', 0))
        ip = ImageProcess(q, centre_coordinate)
        return ip


    def test_findcoordinates(self, imageProcess):
        # Calling _findcoordinates as target function in the process
        # Testing if the Parsing function outputs correct centre coordinates

        ip = imageProcess
        ip.start()                  
        ip.join()
        assert ip.centre_coordinate[0].value >=0
        assert ip.centre_coordinate[1].value >=0
        assert ip.centre_coordinate[0].value == TestClient.centre[0]  # custom defined
        assert ip.centre_coordinate[1].value == TestClient.centre[1]  # custom defined

    

@pytest.mark.asyncio
class TestServer:
    """
    Unit test class to test server functionality
    """
    image_shape = (480, 640, 3)
    dtype = 'uint8' 
    velocity = [2, 2]
    ball_pos = [100, 100]
    radius = 20
    color = (0,0,255)


    @pytest.fixture(scope='class')
    def framegenerator(self):
        pc = RTCPeerConnection()
        framegenerator = FrameGenerator(pc, TestServer.image_shape, TestServer.dtype, TestServer.velocity, TestServer.ball_pos, TestServer.radius, TestServer.color)
        return framegenerator

    
    def test_generateFrame(self, framegenerator):
        # To check if the ball is changing location and the generated frame is correct

        old_pos_x = framegenerator.ball_pos[0] 
        old_pos_y = framegenerator.ball_pos[1]
        frame = framegenerator.generateFrame()
        assert framegenerator.ball_pos[0]  == old_pos_x + framegenerator.velocity[0]
        assert framegenerator.ball_pos[1]  == old_pos_y + framegenerator.velocity[1]
        assert isinstance(frame, np.ndarray)
        assert frame.dtype == np.uint8 

    def test_image_shape(self):
        
        TestServer.image_shape = (-100, -100, -1)
        try:
            pc = RTCPeerConnection()
            framegenerator = FrameGenerator(pc, TestServer.image_shape, TestServer.dtype, TestServer.velocity, TestServer.ball_pos, TestServer.radius, TestServer.color)
            raise Exception("FrameGenerator should raise ValueError as image shape values cannot be negative")
        except ValueError:
            pass 

    def test_image_dtype(self):
        
        TestServer.dtype = 'float64'
        try:
            pc = RTCPeerConnection()
            framegenerator = FrameGenerator(pc, TestServer.image_shape, TestServer.dtype, TestServer.velocity, TestServer.ball_pos, TestServer.radius, TestServer.color)
            raise Exception("FrameGenerator should raise ValueError as shape values should be 'uint8'")
        except ValueError:
            pass 

    def test_ball_velocity(self):
        
        TestServer.velocity = [0,0]
        # Tuple is immutable and velocity should change
        assert not isinstance(TestServer.velocity, tuple)

        try:
            pc = RTCPeerConnection()
            framegenerator = FrameGenerator(pc, TestServer.image_shape, TestServer.dtype, TestServer.velocity, TestServer.ball_pos, TestServer.radius, TestServer.color)
            raise Exception("FrameGenerator should raise ValueError as velocity cannot be zero for a moving ball")
        except ValueError:
            pass 

     
    def test_ball_pos(self):
        TestServer.ball_pos = [-700,700]
        # Tuple is immutable and velocity should change
        assert not isinstance(TestServer.ball_pos, tuple)
        # Ball cannot be outside of the frame
        assert TestServer.ball_pos[1] <= (TestServer.image_shape[0]-TestServer.radius) and TestServer.ball_pos[0] <= (TestServer.image_shape[1]-TestServer.radius)

        try:
            pc = RTCPeerConnection()
            framegenerator = FrameGenerator(pc, TestServer.image_shape, TestServer.dtype, TestServer.velocity, TestServer.ball_pos, TestServer.radius, TestServer.color)
            raise Exception("FrameGenerator should raise ValueError as ball position cannot be negative")
        except ValueError:
            pass 

    def test_ball_radius(self):
        # Constraining radius of the ball 
        TestServer.radius = 5 
        assert TestServer.radius > 0 and TestServer.radius < 40


    def test_ball_color(self):
        TestServer.color = (-3,-3,-3)
        assert TestServer.color[0] >= 0 and TestServer.color[0] <= 255
        assert TestServer.color[1] >= 0 and TestServer.color[1] <= 255
        assert TestServer.color[2] >= 0 and TestServer.color[2] <= 255
        try:
            pc = RTCPeerConnection()
            framegenerator = FrameGenerator(pc, TestServer.image_shape, TestServer.dtype, TestServer.velocity, TestServer.ball_pos, TestServer.radius, TestServer.color)
            raise Exception("FrameGenerator should raise ValueError as image color values cannot be negative")
        except ValueError:
            pass

