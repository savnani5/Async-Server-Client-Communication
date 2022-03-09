# Paras Savnani

import argparse
import asyncio
import logging
import time
import math
import cv2
import numpy as np
from av import VideoFrame

from aiortc import (
    RTCIceCandidate,
    RTCPeerConnection,
    RTCSessionDescription,
    VideoStreamTrack,
)

from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder
from aiortc.contrib.signaling import BYE, add_signaling_arguments, create_signaling


class FrameGenerator(VideoStreamTrack):
    """
    Class responsible for generating bouncing ball frames, send them to client,
    recieve the client coordniates and calculate the error in location of the ball.
    ...

    Attributes
    ----------
    image_shape : tuple of ints
        (height, width, channel) of the image to be generated
    dtype : str
        dtype of the image to be generated
    velocity : list of ints
        (dx, dy) rate of change of ball's position
    ball_pos : list of ints
        (ball_x, ball_y) position of the ball
    radius : int 
        ball radius
    color : tuple of ints
        ball color in bgr color space
    on_message : obj of class 'RTCPeerConnection.createDataChannel.on'
            Function responsible for recieving the ball coordinates from client via datachannel
            and calculate and print the error between actual coordinates and recieved coordinates.
    Methods
    -------
    info : Calculates the ball position in real time and updates the frame generation.
    """
       

    def __init__(self, pc, image_shape, dtype, velocity, ball_pos, radius, color):
        """
        Constructs all the necessary attributes for the FrameGenerator object.

        Parameters
        ----------
        pc : obj of class 'RTCPeerConnection
            To establish the connection
        image_shape : tuple of ints
            (height, width, channel) of the image to be generated
        dtype : str
            dtype of the image to be generated
        velocity : list of ints
            (dx, dy) rate of change of ball's position
        ball_pos : list of ints
            (ball_x, ball_y) position of the ball
        radius : int 
            ball radius
        color : tuple of ints
            ball color in bgr color space
        on_message : obj of class 'RTCPeerConnection.createDataChannel.on'
                Function responsible for recieving the ball coordinates from client via datachannel
                and calculate and print the error between actual coordinates and recieved coordinates.
        """
        super().__init__()
        self.image_shape = image_shape
        self.dtype = dtype
        self.velocity = velocity
        self.ball_pos = ball_pos
        self.radius = radius
        self.color = color

        channel = pc.createDataChannel("chat")
        print(channel.label, "-", "created by local party")

        @channel.on("message")
        def on_message(message):
            print(channel.label, ": Ball Position Recieved from client: ", message)
            coods  = message.split(" ")
            rec_x, rec_y = int(coods[0]), int(coods[1])
            print("Current Ball Position:", self.ball_pos[0], self.ball_pos[1], "\n")
            print("Distance Error: ", round(math.sqrt((self.ball_pos[0]-rec_x)**2 + (self.ball_pos[1]-rec_y)**2), 3), "\n")

    def generateFrame(self):
        """
        Method responsible to generating the frames and updating the ball's location each time it is called

        Parameters
        ----------
        None

        Returns
        -------
        frame : numpy ndarray
            Image continaing the updated postion of the ball 
        """

        # print(self.ball_x, self.ball_y, "/n")
        # Ball Position Update
        self.ball_pos[0] += self.velocity[0]
        self.ball_pos[1] += self.velocity[1]

        # Change the sign of increment on collision with the boundary
        if self.ball_pos[1] >= (self.image_shape[0] - self.radius) or (self.ball_pos[1] - self.radius) <= 0:
            self.velocity[1] *= -1

        if self.ball_pos[0] >= (self.image_shape[1]-self.radius) or (self.ball_pos[0] - self.radius) <= 0:
            self.velocity[0] *= -1

        # generate frame
        height, width, channel = self.image_shape
        frame = np.zeros((height, width, channel),dtype=self.dtype)
        cv2.circle(frame,(self.ball_pos[0], self.ball_pos[1]),self.radius, self.color,-1)

        return frame

    async def recv(self):
        """
        Method responsible to call function to generate frame and 
        convert them to appropriate object for Mediatrack channel.

        Parameters
        ----------
        None

        Returns
        -------
        frame : obj of class 'Videoframe'
            Compatible format for transferring via Media channel
        """
        pts, time_base = await self.next_timestamp()

        frame = self.generateFrame()
        
        # Convert to VideoFrame object
        frame = VideoFrame.from_ndarray(frame, format='bgr24')

        frame.pts = pts
        frame.time_base = time_base
        return frame


async def server_consume_signaling(pc, signaling, loop):
    """
    Asynchronoulsy wait for the answer to establish connection.

    Parameters
    ----------
    pc : obj of class 'RTCPeerConnection
            To establish the connection
    signaling :  obj of class 'aiortc.contrib.signaling.create_signaling'
    loop : obj of class 'asyncio.get_event_loop'
        Event loop object for async coroutines 

    Returns
    ----------
    None
    """
    try:
        while True:
            obj = await signaling.receive()
            
            if isinstance(obj, RTCSessionDescription):
                await pc.setRemoteDescription(obj)
                

            elif isinstance(obj, RTCIceCandidate):
                await pc.addIceCandidate(obj)
            elif obj is BYE:
                print("Exiting")
                break
    except:
        # Stop the loop if input object is invalid
        loop.stop()
    
        print("Shutdown complete ...") 


async def offer(pc, signaling, loop):
    """
    Generate offer with media and datachannel transimission and connection 
    with the client.

    Parameters
    ----------
    pc : obj of class 'RTCPeerConnection
            To establish the connection
    signaling :  obj of class 'aiortc.contrib.signaling.create_signaling'
    recorder : obj of class 'MediaRecorder'
        For recording te incoming image frames to a video
    loop : obj of class 'asyncio.get_event_loop'
        Event loop object for async coroutines 

    Returns
    ----------
    None
    """
    # connect signaling
    await signaling.connect()

    # Create Instance of FrameGenerator
    image_shape = (480, 640, 3)
    dtype = 'uint8' 
    velocity = [2, 2]
    ball_pos = [100, 100]
    radius = 20
    color = (0,0,255)


    def add_tracks():
        framegenerator = FrameGenerator(pc, image_shape, dtype, velocity, ball_pos, radius, color)
        pc.addTrack(framegenerator)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print("Connection state is ", pc.connectionState)
        if pc.connectionState == "failed":
            await pc.close()    

    # send offer
    add_tracks()
    await pc.setLocalDescription(await pc.createOffer())
    await signaling.send(pc.localDescription)

    print("Server Side to send Video frames to the client....\n")

    # consume signaling
    await server_consume_signaling(pc, signaling, loop)

 

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Server Side- Generate frames of images and sends to client")
    parser.add_argument("--verbose", "-v", action="count")
    add_signaling_arguments(parser)
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    # create signaling and peer connection
    signaling = create_signaling(args)
    pc = RTCPeerConnection()

    # run event loop
    loop = asyncio.get_event_loop()

    try:
        asyncio.ensure_future(offer(
                pc=pc,
                signaling=signaling,
                loop=loop))
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        # cleanup
        loop.run_until_complete(signaling.close())
        loop.run_until_complete(pc.close())

