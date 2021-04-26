import argparse
import json
import os
import sys
import time

import cv2
import numpy as np
import requests
from unidecode import unidecode

from modules import HeadposeDetector


CONFIG_PATH = "app-data/config/data.json"
MODEL_PATH = "app-data/model/shape_predictor_68_face_landmarks.dat"
TRIVIA_API_URL = "https://opentdb.com/api.php?amount=10&category=19&type=boolean"

def load_json(file_path: str):
    """load data from file""" 
    with open(file_path) as f:
        data = json.load(f)
    return data

def call_trivia_api(url: str):
    """download data from trivia api"""
    print("downloading data - trivia api")
    r = requests.get("https://opentdb.com/api.php?amount=10&category=19&type=boolean")
    return r.json()

def display_result(user_score: int, n_of_questions: int):
    """download data from trivia api
    Args:
        user_score: int
        n_of_questions: int

    """
    result_frame = np.zeros((500, 500, 3), np.uint8) #create blank image
    result_frame[:] = (0, 0, 255) #fill color
    cv2.rectangle(result_frame, (0, result_frame.shape[0]-100), (result_frame.shape[1], result_frame.shape[0]), (255, 0, 0), -1)
    cv2.putText(result_frame,f"Score: {user_score} / {n_of_questions}" , (int(result_frame.shape[1]/3-30),int(result_frame.shape[0]/2-30)), cv2.FONT_HERSHEY_SIMPLEX, 1,(255,255,255),1,cv2.LINE_AA)
    cv2.putText(result_frame,"press any key to quit!" , (int(result_frame.shape[1]/3-30),int(result_frame.shape[0]-50)), cv2.FONT_HERSHEY_SIMPLEX, 0.5,(255,255,255),1,cv2.LINE_AA)
    cv2.imshow('Game', result_frame)
    cv2.waitKey(0) #display 10 seconds
    cv2.destroyAllWindows()
    sys.exit()



def run(source: str = "local"):

    user_score = 0

    q_text = ""
    q_ans = ""
    q_point = 0
    
    data = None
    questions = None

    if source == "local":
        data = load_json(CONFIG_PATH) #read data from file
        questions = iter(data["items"])
        n_of_questions = len(data["items"])
    elif source == "trivia":
        data = call_trivia_api(TRIVIA_API_URL) # read data from url
        questions = iter(data["results"])
        n_of_questions = len(data["results"])
    else:
        print("invalid source!")
        sys.exit()

    # read timeout values from config if available, else set defaults
    game_timeout = data["game_timeout"] if "game_timeout" in data else 60
    question_timeout = data["question_timeout"] if "question_timeout" in data else 10

    headpose_detector = HeadposeDetector.HeadposeDetector(model_path=MODEL_PATH)

    #video capture
    cap = cv2.VideoCapture(0)

    #set height and width
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 960)

    
    elapsed_time = 0
    elapsed_time_question = 0

    start_time = time.time()
    start_time_question = time.time()

    go_to_next_question=True

    while True:
        
        if go_to_next_question:
            try:
                question = next(questions) #get new question
            except StopIteration: #no more questions
                print("no more question!")
                display_result(user_score, n_of_questions)
                
            start_time_question = time.time() #reset question time
            go_to_next_question = False
        
        # calculate elapsed time
        elapsed_time_question = time.time() - start_time_question
        elapsed_time = time.time() - start_time

        # timeout control for game
        if elapsed_time > game_timeout:
            print("game finished! (timeout)")
            display_result(user_score, n_of_questions)

        # timeout control for question
        if elapsed_time_question > question_timeout:
            print("skipping to next question! (timeout)")
            go_to_next_question = True

        # prepare question
        q_text = question["question"]
        q_ans = question["correct_answer"]
        q_point = question["point"] if "point" in question else 1 #no point information exists in trivia!, set point=1 for each question

        #read frame from camera
        ret, frame = cap.read()
        if not ret or frame is None:
            break
    
        frame = cv2.flip(frame, 1) # flip frame 

        frame_orig = frame.copy() # keep original frame

        # detect faces and head rotations
        frame, angles, faceDetected = headpose_detector.process_image(frame)
        
        answer = "NA"

        # if face detected
        if faceDetected:
            [X, Y, Z] = angles
            
            #check head rotation
            if Z < -30: 
                answer = "False"
                cv2.rectangle(frame, (int(frame.shape[1]/2), frame.shape[0]-100), (frame.shape[1], frame.shape[0]), (0, 0, 255), -1)
                cv2.putText(frame,"FALSE" , (int(frame.shape[1]/2+30),frame.shape[0]-50), cv2.FONT_HERSHEY_SIMPLEX, 1.5,(255,255,255),1,cv2.LINE_AA)
            elif Z > 30:
                answer = "True"
                cv2.rectangle(frame, (0, frame.shape[0]-100), (int(frame.shape[1]/2), frame.shape[0]), (0, 255, 0), -1)
                cv2.putText(frame,"TRUE" , (30,frame.shape[0]-50), cv2.FONT_HERSHEY_SIMPLEX, 1.5,(0,0,0),1,cv2.LINE_AA)            
            else:
                answer = "NA"
                # add default informations to frame
                cv2.rectangle(frame, (0, frame.shape[0]-35), (int(frame.shape[1]/2), frame.shape[0]), (0, 255, 0), -1)
                cv2.putText(frame," "*10+"TRUE"+" "*10+"<"*3, (int(frame.shape[1]/2-frame.shape[1]*0.25),int(frame.shape[0]-15)), cv2.FONT_HERSHEY_SIMPLEX, 0.5,(0,0,0),1,cv2.LINE_AA)
                
                cv2.rectangle(frame, (int(frame.shape[1]/2), frame.shape[0]-35), (frame.shape[1], frame.shape[0]), (0, 0, 255), -1)
                cv2.putText(frame,">"*3 + " "*10 + "FALSE", (int(frame.shape[1]/2+frame.shape[1]*0.08),frame.shape[0]-15), cv2.FONT_HERSHEY_SIMPLEX, 0.5,(255,255,255),1,cv2.LINE_AA)

        #compare answers
        show_question_result = False
        if answer == q_ans:
            # show result
            cv2.rectangle(frame_orig, (0, frame_orig.shape[0]-35), (frame_orig.shape[1], frame_orig.shape[0]), (0, 255, 0), -1)
            cv2.putText(frame_orig,f"Correct! +{q_point} points", (int(frame_orig.shape[1]/2-30),frame_orig.shape[0]-15), cv2.FONT_HERSHEY_SIMPLEX, 0.5,(0,0,0),1,cv2.LINE_AA)
            user_score += q_point
            show_question_result = True
                     
        elif answer != "NA":
            # show result
            cv2.rectangle(frame_orig, (0, frame_orig.shape[0]-35), (frame_orig.shape[1], frame_orig.shape[0]), (0, 0, 255), -1)
            cv2.putText(frame_orig,f"Wrong answer!", (int(frame_orig.shape[1]/2-30),frame_orig.shape[0]-15), cv2.FONT_HERSHEY_SIMPLEX, 0.5,(255,255,255),1,cv2.LINE_AA)
            show_question_result = True

        if show_question_result:
            cv2.imshow('Game', frame_orig)
            cv2.waitKey(1500) #display x seconds
            go_to_next_question = True
            show_question_result = False
            

        # show question
        # optimize font size
        font_size = 0.7
        if len(q_text) > 100:
            font_size = 0.5

        cv2.rectangle(frame, (0, 0), (frame.shape[1], 70), (255, 0, 0), -1)
        cv2.putText(frame, unidecode(q_text) , (10, 50), cv2.FONT_HERSHEY_SIMPLEX, font_size, (255,255,255), 1, cv2.LINE_AA)
        cv2.putText(frame, "Q:"+str(int(question_timeout - elapsed_time_question)) , (frame.shape[1]-50, frame.shape[0]-60), cv2.FONT_HERSHEY_SIMPLEX, 0.6,(255,255,255),1,cv2.LINE_AA)
        cv2.putText(frame, "T:"+str(int(game_timeout - elapsed_time)) , (frame.shape[1]-50, frame.shape[0]-40), cv2.FONT_HERSHEY_SIMPLEX, 0.6,(255,255,255),1,cv2.LINE_AA)
        
        # show final frame
        cv2.imshow('Game', frame)
        if cv2.waitKey(1) == ord('q'):
            break
        
    cv2.destroyAllWindows()
    cap.release()
    
    del frame
    del cap

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--source", type=str, default="local", choices={"local", "trivia"}, help='data source')
    args = parser.parse_args()
    run(args.source)