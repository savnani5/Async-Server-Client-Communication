# Paras Savnani

import argparse
import asyncio
import logging
import math
import time
import cv2
import multiprocessing as mp
import numpy as np
from av import VideoFrame

from aiortc import (
    RTCIceCandidate,
    RTCPeerConnection,
    RTCSessionDescription,
    MediaStreamTrack,
)
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder, MediaRelay
from aiortc.contrib.signaling import BYE, add_signaling_arguments, create_signaling
        


class ImageProcess(mp.Process):
    """
    Class to process the image frame to find ball centre coordinates
    ...

    Attributes
    ----------
    queue : obj of class 'multiprocessing.queue'
        multiprocessing queue to store frames
    centre_coordinate : tuple of objs of class 'multiprocessing.value'
        centre coordinate of the ball
    target : obj of class 'ImageProcess'
        input target function for multiprocessing queue to find coordinates

    Methods
    -------
    info : Method responsible for Parsing the incoming frame, finding and storing the 
        centre coordinate of the ball and displaying the corresponding frame.
    """

    def __init__(self, queue, centre_coordinate, target=None):    
        """
        Constructs all the necessary attributes for the ImageProcess object.

        Parameters
        ----------
        queue : obj of class 'multiprocessing.queue'
            multiprocessing queue to store frames
        centre_coordinate : tuple of objs of class 'multiprocessing.value'
            centre coordinate of the ball
        target : obj of class 'ImageProcess'
            input target function for multiprocessing queue to find coordinates
        """
        self.queue = queue
        self.centre_coordinate = centre_coordinate
        self.target = self._findCoordinates
        mp.Process.__init__(self, target=self.target)

    def _findCoordinates(self):
        """
        Method responsible for Parsing the incoming frame, finding and storing the 
        centre coordinate of the ball and displaying the corresponding frame.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        frame = self.queue.get()
        # Threshold the image to get the mask for the ball - in realistic scenarios hsv range masking is used to detect a particular colour due to intensity variations.
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _,thresh = cv2.threshold(gray,50,255,cv2.THRESH_BINARY)

        # calculate moments of binary image
        M = cv2.moments(thresh)

        # calculate x,y coordinate of center
        cX = int(M["m10"] / M["m00"])
        cY = int(M["m01"] / M["m00"])

        # print(cX, cY, "\n")
        # put text and highlight the center
        cv2.circle(frame, (cX, cY), 5, (255, 255, 0), -1)
        cv2.putText(frame, f"{cX}, {cY}", (cX - 25, cY - 25),cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
        
        cv2.imshow('img', frame)
        cv2.waitKey(100)

        # Store Coordinates as multiprocessing Values
        self.centre_coordinate[0].value = cX
        self.centre_coordinate[1].value = cY

        

class FrameReceiever(MediaStreamTrack):
    """
    Class to asynchronous;y recieve the frame and start the 
    process to parse it for the centre coordinate.
    ...

    Class Attributes
    ----------
    kind : str
        type of media track
    queue : obj of class 'multiprocessing.queue'
        multiprocessing queue to store frames
    channel : obj of class 'RTCPeerConnection.createDataChannel'
        input target function for multiprocessing queue to find coordinates
    centre_coordinate : tuple of objs of class 'multiprocessing.value'
            centre coordinate of the ball
    
    Instance Attributes
    ----------
    track : obj of class 'MediaStreamTrack'
        To recieve frames asynchronously 
    on_datachannel : obj of class 'RTCPeerConnection'
        Establishing the data channel on client side to transfer coordinates

    Methods
    -------
    info : Uses Image process class to process images and send coordinates to the server
    """
    
    kind = "video"
    queue = mp.Queue()                                       # Multiprocessing queue
    channel = None                                           # Assigned when Class is initialized
    centre_coordinate = (mp.Value('i', 0), mp.Value('i', 0)) # Using multiprocessing values as shared memory 


    def __init__(self, pc, track):
        """
        Constructs all the necessary attributes for the FrameReceiever object.

        Parameters
        ----------
        pc : obj of class 'RTCPeerConnection
            To establish the connection
        track : obj of class 'MediaStreamTrack'
            To recieve frames asynchronously 
        on_datachannel : obj of class 'RTCPeerConnection.on'
            Establishing the data channel on client side to transfer coordinates
        """
        super().__init__()
        self.track = track

        @pc.on("datachannel")
        def on_datachannel(channel):
            FrameReceiever.channel = channel
            print(FrameReceiever.channel.label, "-", "created by remote party")
        
    async def send_coordinates():
        """
        Method responsible to generate message and send it to server uisng channel object.
        """
        message = str(FrameReceiever.centre_coordinate[0].value) + " " + str(FrameReceiever.centre_coordinate[1].value)
        FrameReceiever.channel.send(message)


    async def recv(self):
        """
        Method responsible to asynchronoulsy recieve the frames, 
        call function to process them adn convert them to appropriate object for Mediatrack.

        Parameters
        ----------
        None

        Returns
        -------
        new_frame : obj of class 'Videoframe'
            Compatible format for transferring via Media channel
        """
        frame = await self.track.recv()
         
        img = frame.to_ndarray(format="bgr24")
        FrameReceiever.queue.put(img)
        process_a = ImageProcess(FrameReceiever.queue, FrameReceiever.centre_coordinate)
        process_a.start()

        # Send coordinates to server.py
        asyncio.ensure_future(FrameReceiever.send_coordinates())

        # rebuild a VideoFrame, preserving timing information
        new_frame = VideoFrame.from_ndarray(img, format="bgr24")
        new_frame.pts = frame.pts
        new_frame.time_base = frame.time_base
        return new_frame



async def client_consume_signaling(pc, signaling, loop):
    """
    Asynchronoulsy wait for the signals, record the video frames 
    and send answer to the corresponding offer. 

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
                await recorder.start()

                if obj.type == "offer":
                    # send answer
                    await pc.setLocalDescription(await pc.createAnswer())
                    await signaling.send(pc.localDescription)
                    
            elif isinstance(obj, RTCIceCandidate):
                await pc.addIceCandidate(obj)
            elif obj is BYE:
                print("Exiting")
                break
    except:
        # Stop the loop if input object is invalid
        loop.stop()

        print("Shutdown complete ...") 


async def answer(pc, signaling, recorder, loop):
    """
    Asynchronoulsy wait for the signal and generate and answer for offer, 
    generate media and data channels to recieve corresponding data and consume signaling.

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

    # Media Channel to receive frames
    @pc.on("track")
    def on_track(track):      
        print("Receiving %s" % track.kind)

        framereceiver = FrameReceiever(pc, track) 
        pc.addTrack(framereceiver)
        recorder.addTrack(track)
        

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print("Connection state is ", pc.connectionState)
        if pc.connectionState == "failed":
            await pc.close()
    
    # consume signaling
    await client_consume_signaling(pc, signaling, loop)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Client Side - Sends coordinates to Server")
    parser.add_argument("--record-to", help="Write received media to a file."),
    parser.add_argument("--verbose", "-v", action="count")
    add_signaling_arguments(parser)
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    # create signaling and peer connection
    signaling = create_signaling(args)
    pc = RTCPeerConnection()

    # create media sink
    if args.record_to:
        recorder = MediaRecorder(args.record_to)
    else:
        recorder = MediaBlackhole()

    # run event loop
    loop = asyncio.get_event_loop()
    try:
        asyncio.ensure_future(answer(
                pc=pc,
                recorder=recorder,
                signaling=signaling,
                loop=loop))
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        # cleanup
        cv2.destroyAllWindows()
        loop.run_until_complete(recorder.stop())
        loop.run_until_complete(signaling.close())
        loop.run_until_complete(pc.close())
