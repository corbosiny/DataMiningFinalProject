import argparse, retro, threading, os, numpy, random, math
from Agent import Agent
from LossHistory import LossHistory

import tensorflow as tf
from tensorflow.python import keras
from keras.models import Sequential
from keras.layers import Dense
from keras.optimizers import Adam
from keras.models import load_model
from keras import backend as K
import keras.losses
from collections import deque

class DeepQAgent(Agent):
    """An agent that implements the Deep Q Neural Network Reinforcement Algorithm to learn street fighter 2"""
    
    EPSILON_MIN = 0.1                                         # Minimum exploration rate for a trained model
    DEFAULT_EPSILON_DECAY = 0.999                             # How fast the exploration rate falls as training persists
    DEFAULT_DISCOUNT_RATE = 0.98                              # How much future rewards influence the current decision of the model
    DEFAULT_LEARNING_RATE = 0.0001

    # Mapping between player state values and their one hot encoding index
    stateIndices = {512 : 0, 514 : 1, 516 : 2, 518 : 3, 520 : 4, 522 : 5, 524 : 6, 526 : 7, 532 : 8} 
    doneKeys = [0, 528, 530, 1024, 1026, 1028, 1030, 1032]

    ACTION_BUTTONS = ['X', 'Y', 'Z', 'A', 'B', 'C']

    def _huber_loss(y_true, y_pred, clip_delta=1.0):
        error = y_true - y_pred
        cond  = K.abs(error) <= clip_delta

        squared_loss = 0.5 * K.square(error)
        quadratic_loss = 0.5 * K.square(clip_delta) + clip_delta * (K.abs(error) - clip_delta)

        return K.mean(tf.where(cond, squared_loss, quadratic_loss))

    def __init__(self, stateSize= 32, actionSize= 38, game= 'StreetFighterIISpecialChampionEdition-Genesis', load= False, epsilon= 1, name= None):
        """Initializes the agent and the underlying neural network

        Parameters
        ----------
        stateSize
            The number of features that will be fed into the Agent's network
        
        actionSize
            The size of the possible buttons the Agent can press during a fight

        game
            A String of the game the Agent will be making an environment of, defaults to StreetFighterIISpecialChampionEdition-Genesis

        name
            A string representing the name of the agent that will be used when saving the model and training logs
            Defaults to the class name if none is provided

        Returns
        -------
        None
        """
        self.stateSize = stateSize
        self.actionSize = actionSize
        self.gamma = DeepQAgent.DEFAULT_DISCOUNT_RATE         # discount rate
        if load: self.epsilon = DeepQAgent.EPSILON_MIN        # If the model is already trained lower the exploration rate
        else: self.epsilon = epsilon                          # If the model is not trained set a high initial exploration rate
        self.epsilonDecay = DeepQAgent.DEFAULT_EPSILON_DECAY  # How fast the exploration rate falls as training persists
        self.learningRate = DeepQAgent.DEFAULT_LEARNING_RATE 
        self.lossHistory = LossHistory()
        super(DeepQAgent, self).__init__(game= game, render= render, load= load, name= name) 

    def isActionableState(self, info, action = 0):
        """Determines if the Agent has control over the game in it's current state(the Agent is in hit stun, ending lag, etc.)

        Parameters
        ----------
        action
            The last action taken by the Agent

        info
            The RAM info of the current game state the Agent is presented with as a dictionary of keyworded values from Data.json

        Returns
        -------
        isActionable
            A boolean variable describing whether the Agent has control over the given state of the game
        """
        action = self.environment.get_action_meaning(action)
        if info['round_timer'] == 39208:
            return False
        else:
            return True
        # elif info['status'] == 516 and any([button in action for button in DeepQAgent.ACTION_BUTTONS]):
        #     return False
        # elif info['status'] not in [512, 514, 516]:
        #     return False
        # else:
        #     return True

    def getMove(self, obs, info):
        """Returns a set of button inputs generated by the Agent's network after looking at the current observation

        Parameters
        ----------
        obs
            The observation of the current environment, 2D numpy array of pixel values

        info
            An array of information about the current environment, like player health, enemy health, matches won, and matches lost, etc.
            A full list of info can be found in data.json

        Returns
        -------
        move
            A set of button inputs in a multivariate array of the form Up, Down, Left, Right, A, B, X, Y, L, R.
        """
        if not self.isActionableState(info):
            return Agent.NO_MOVE
        elif numpy.random.rand() <= self.epsilon:
            move = self.getRandomMove()
            return move
        else:
            stateData = self.prepareNetworkInputs(info)
            move = self.model.predict(stateData)[0]
            #print('Q values: ', move)
            move = numpy.argmax(move)
            return move

    def initializeNetwork(self):
        """Initializes a Neural Net for a Deep-Q learning Model
        
        Parameters   
        ----------
        None

        Returns
        -------
        model
            The initialized neural network model that Agent will interface with to generate game moves
        """
        # model = Sequential()
        # model.add(Dense(48, input_dim= self.stateSize, activation='relu'))
        # model.add(Dense(96, activation='relu'))
        # model.add(Dense(96, activation='relu'))
        # model.add(Dense(96, activation='relu'))
        # model.add(Dense(48, activation='relu'))
        # model.add(Dense(self.actionSize, activation='linear'))
        # model.compile(loss=DeepQAgent._huber_loss, optimizer=Adam(lr=self.learningRate))

        # model = Sequential()
        # model.add(Dense(256, input_dim= self.stateSize, activation='relu'))
        # model.add(Dense(256, activation='relu'))
        # model.add(Dense(512, activation='relu'))
        # model.add(Dense(1024, activation='relu'))
        # model.add(Dense(512, activation='relu'))
        # model.add(Dense(256, activation='relu'))
        # model.add(Dense(256, activation='relu'))
        # model.add(Dense(self.actionSize, activation='linear'))
        # model.compile(loss=DeepQAgent._huber_loss, optimizer=Adam(lr=self.learningRate))

        model = Sequential()
        model.add(Dense(4096, input_dim= self.stateSize, activation='relu'))
        model.add(Dense(4096, activation='relu'))
        model.add(Dense(2048, activation='relu'))
        model.add(Dense(2048, activation='relu'))
        model.add(Dense(1024, activation='relu'))
        model.add(Dense(1024, activation='relu'))
        model.add(Dense(512, activation='relu'))
        model.add(Dense(256, activation='relu'))
        model.add(Dense(128, activation='relu'))
        model.add(Dense(self.actionSize, activation='linear'))
        model.compile(loss=DeepQAgent._huber_loss, optimizer=Adam(lr=self.learningRate))

        print('Successfully initialized model')
        return model

    def prepareMemoryForTraining(self, memory):
        """prepares the recorded fight sequences into training data
        
        Parameters
        ----------
        memory
            A 2D array where each index is a recording of a state, action, new state, and reward sequence
            See readme for more details

        Returns
        -------
        data
            The prepared training data in whatever from the model needs to train
            DeepQ needs a state, action, and reward sequence to train on
            The observation data is thrown out for this model for training
        """
        data = []
        for step in self.memory:
            data.append(
            [self.prepareNetworkInputs(step[Agent.STATE_INDEX]), 
            step[Agent.ACTION_INDEX], 
            step[Agent.REWARD_INDEX],
            step[Agent.DONE_INDEX],
            self.prepareNetworkInputs(step[Agent.NEXT_STATE_INDEX])])

        return data

    def prepareNetworkInputs(self, step):
        """Generates a feature vector from the current game state information to feed into the network
        
        Parameters
        ----------
        step
            A given set of state information from the environment
            
        Returns
        -------
        feature vector
            An array extracted from the step that is the same size as the network input layer
            Takes the form of a 1 x 30 array. With the elements:
            enemy_health, enemy_x, enemy_y, 8 one hot encoded enemy state elements, 
            8 one hot encoded enemy character elements, player_health, player_x, player_y, and finally
            8 one hot encoded player state elements.
        """
        feature_vector = []
        
        # Enemy Data
        feature_vector.append(step["enemy_health"])
        feature_vector.append(step["enemy_x_position"])
        feature_vector.append(step["enemy_y_position"])

        # one hot encode enemy state
        # enemy_status - 512 if standing, 514 if crouching, 516 if jumping, 518 blocking, 522 if normal attack, 524 if special attack, 526 if hit stun or dizzy, 532 if thrown
        oneHotEnemyState = [0] * len(DeepQAgent.stateIndices.keys())
        if step['enemy_status'] not in DeepQAgent.doneKeys: oneHotEnemyState[DeepQAgent.stateIndices[step["enemy_status"]]] = 1
        feature_vector += oneHotEnemyState

        # one hot encode enemy character
        oneHotEnemyChar = [0] * 8
        oneHotEnemyChar[step["enemy_character"]] = 1
        feature_vector += oneHotEnemyChar

        # Player Data
        feature_vector.append(step["health"])
        feature_vector.append(step["x_position"])
        feature_vector.append(step["y_position"])

        # player_status - 512 if standing, 514 if crouching, 516 if jumping, 520 blocking, 522 if normal attack, 524 if special attack, 526 if hit stun or dizzy, 532 if thrown
        oneHotPlayerState = [0] * len(DeepQAgent.stateIndices.keys())
        if step['status'] not in DeepQAgent.doneKeys: oneHotPlayerState[DeepQAgent.stateIndices[step["status"]]] = 1
        feature_vector += oneHotPlayerState

        feature_vector = numpy.reshape(feature_vector, [1, self.stateSize])
        return feature_vector

    def trainNetwork(self, data, model):
        """To be implemented in child class, Runs through a training epoch reviewing the training data
        Parameters
        ----------
        data
            The training data for the model to train on, a 2D array of state, action, reward, sequence

        model
            The model to train and return the Agent to continue playing with
        Returns
        -------
        model
            The input model now updated after this round of training on data
        """
        minibatch = random.sample(data, len(data))
        self.lossHistory.losses_clear()
        for state, action, reward, done, next_state in minibatch:     
            modelOutput = model.predict(state)[0]
            if not done:
                reward = (reward + self.gamma * numpy.amax(model.predict(next_state)[0]))

            modelOutput[action] = reward
            modelOutput = numpy.reshape(modelOutput, [1, self.actionSize])
            model.fit(state, modelOutput, epochs= 1, verbose= 0, callbacks= [self.lossHistory])

        if self.epsilon > DeepQAgent.EPSILON_MIN: self.epsilon *= self.epsilonDecay
        return model


from keras.utils.generic_utils import get_custom_objects
loss = DeepQAgent._huber_loss
get_custom_objects().update({"_huber_loss": loss})

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description= 'Processes agent parameters.')
    parser.add_argument('-r', '--render', action= 'store_true', help= 'Boolean flag for if the user wants the game environment to render during play')
    parser.add_argument('-l', '--load', action= 'store_true', help= 'Boolean flag for if the user wants to load pre-existing weights')
    parser.add_argument('-e', '--episodes', type= int, default= 10, help= 'Intger representing the number of training rounds to go through, checkpoints are made at the end of each episode')
    parser.add_argument('-n', '--name', type= str, default= None, help= 'Name of the instance that will be used when saving the model or it\'s training logs')
    args = parser.parse_args()
    qAgent = DeepQAgent(load= args.load, name= args.name)
    qAgent.train(review= True, episodes= args.episodes)
