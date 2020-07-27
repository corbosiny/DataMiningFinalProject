import argparse, retro, threading, os, numpy, time
from collections import deque

from tensorflow.python import keras
from keras.models import load_model

class Agent():
    """ Abstract class that user created Agents should inherit from.
        Contains helper functions for launching training environments and generating training data sets.
    """

    # The indices representing what each index in a training point represent
    OBSERVATION_INDEX = 0                                                                          # The current display image of the game state
    STATE_INDEX = 1                                                                                # The state the agent was presented with    
    ACTION_INDEX = 2                                                                               # The action the agent took
    REWARD_INDEX = 3                                                                               # The reward the agent received for that action
    NEXT_OBSERVATION_INDEX = 4                                                                     # The current display image of the new state the action led to
    NEXT_STATE_INDEX = 5                                                                           # The next state that the action led to
    DONE_INDEX = 6                                                                                 # A flag signifying if the game is over

    MAX_DATA_LENGTH = 50000                                                                        # Max number of decision frames the Agent can remember from a fight, average is about 2000 per fight

    DEFAULT_MODELS_DIR_PATH = '../models'                                                          # Default path to the dir where the trained models are saved for later access
    DEFAULT_LOGS_DIR_PATH = '../logs'                                                              # Default path to the dir where training logs are saved for user review
    
    ### End of static variables 

    ### Static Methods
    def getStates():
        """Static method that gets and returns a list of all the save state names that can be loaded

        Parameters
        ----------
        None

        Returns
        -------
        states
            A list of strings where each string is the name of a different save state
        """
        files = os.listdir('../StreetFighterIISpecialChampionEdition-Genesis')
        states = [file.split('.')[0] for file in files if file.split('.')[1] == 'state']
        return states

    def convertMoveToFrameInputs(move):
        """Converts the desired move into a series of frame inputs in order to acomplish that move

        Parameters
        ----------
        move
            enum type named after the move to be performed
            is used as the key into the move to inputs dic

        Returns
        -------

        frameInputs
            An iterable frame inputs object containing the frame by frame input buffer for the move
        """
        pass

    ### End of static methods

    ### Object methods

    def __init__(self, load= False, name= None):
        """Initializes the agent and the underlying neural network

        Parameters
        ----------
        load
            A boolean flag that specifies whether to initialize the model from scratch or load in a pretrained model

        name
            A string representing the name of the model that will be used when saving the model and the training logs
            Defaults to the class name if none are provided

        Returns
        -------
        None
        """
        if name is None: self.name = self.__class__.__name__
        else: self.name = name
        self.prepareForNextFight()

        if self.__class__.__name__ != "Agent":
            self.model = self.initializeNetwork()    								            # Only invoked in child subclasses, Agent has no network
            if load: self.loadModel()

    def prepareForNextFight(self):
        """Clears the memory of the fighter so it can prepare to record the next fight"""
        self.memory = deque(maxlen= Agent.MAX_DATA_LENGTH)                                     # Double ended queue that stores states during the game


    def getRandomMove(self, action_space):
        """Returns a random set of button inputs

        Parameters
        ----------
            action_space
                The list of possible actions the Agent can take in the environment

        Returns
        -------
            move 
                A random selection from the action_space of the environment
        """
        move = action_space.sample()                                              # Take random sample of all the button press inputs the Agent could make
        return move                                

    def recordStep(self, observation, state, reward, nextObservation, nextState, done):
        """Records the last observation, action, reward and the resultant observation about the environment for later training
        Parameters
        ----------
        observation
            The current display image in the form of a 2D array containing RGB values of each pixel

        state
            The state the Agent was presented with before it took an action.
            A dictionary containing tagged RAM data

        reward
            The reward the agent received for taking that action

        nextObservation
            The resultant display image in the form of a 2D array containing RGB values of each pixel

        nextState
            The state that the chosen action led to

        done
            Whether or not the new state marks the completion of the emulation

        Returns
        -------
        None
        """
        self.memory.append((observation, state, self.lastAction, reward, nextObservation, nextState, done)) # Steps are stored as tuples to avoid unintended changes

    def reviewFight(self):
        """The Agent goes over the data collected from it's last fight, prepares it, and then runs through one epoch of training on the data"""
        data = self.prepareMemoryForTraining(self.memory)
        self.model = self.trainNetwork(data, self.model)   		                           # Only invoked in child subclasses, Agent does not learn
        self.saveModel()
        self.prepareForNextFight()

    def loadModel(self):
        """Loads in pretrained model object ../models/{Instance_Name}Model
        Parameters
        ----------
        None

        Returns
        -------
        model
            The loaded model of the agent from the specified file
        """
        self.model.load_weights(os.path.join(Agent.DEFAULT_MODELS_DIR_PATH, self.getModelName()))
        print("Model successfully loaded")

    def saveModel(self):
        """Saves the currently trained model in the default naming convention ../models/{Instance_Name}Model
        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        self.model.save_weights(os.path.join(Agent.DEFAULT_MODELS_DIR_PATH, self.getModelName()))
        print('Checkpoint established. model successfully saved')
        with open(os.path.join(Agent.DEFAULT_LOGS_DIR_PATH, self.getLogsName()), 'a+') as file:
            file.write(str(sum(self.lossHistory.losses) / len(self.lossHistory.losses)))
            file.write('\n')

    def getModelName(self):
        """Returns the formatted model name for the current model"""
        return  self.name + "Model"

    def getLogsName(self):
        """Returns the formatted log name for the current model"""
        return self.name + "Logs"

    ### End of object methods

    ### Abstract methods for the child Agent to implement
    def getMove(self, action_space, obs, info):
        """Returns a set of button inputs generated by the Agent's network after looking at the current observation

        Parameters
        ----------
        action_space
            The list of possible moves the Agent can take in this environment

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
        move = self.getRandomMove(action_space)
        self.lastAction = move
        frameInputs = Agent.convertMoveToFrameInputs(move)
        return frameInputs

    def initializeNetwork(self):
        """To be implemented in child class, should initialize or load in the Agent's neural network
        
        Parameters
        ----------
        None

        Returns
        -------
        model
            A newly initialized model that the Agent will use when generating moves
        """
        raise NotImplementedError("Implement this is in the inherited agent")
    
    def prepareMemoryForTraining(self, memory):
        """To be implemented in child class, should prepare the recorded fight sequences into training data
        
        Parameters
        ----------
        memory
            A 2D array where each index is a recording of a state, action, new state, and reward sequence
            See readme for more details

        Returns
        -------
        data
            The prepared training data
        """
        raise NotImplementedError("Implement this is in the inherited agent")

    def trainNetwork(self, data, model):
        """To be implemented in child class, Runs through a training epoch reviewing the training data and returns the trained model
        Parameters
        ----------
        data
            The training data for the model
        
        model
            The model for the function to train

        Returns
        -------
        model
            The now trained and hopefully improved model
        """
        raise NotImplementedError("Implement this is in the inherited agent")

    ### End of Abstract methods



# Test code where an example environment is created and an Agent plays the game by randomly sampling the action space at each decision
# The user can specify the -r flag to render the test envionrments
def testMain(agent, render= False):
    env = retro.make(game= 'StreetFighterIISpecialChampionEdition-Genesis',  state= "chunli")
    obs, info = env.reset(), None
    while True:
        action = agent.getMove(env.action_space, obs, info)
        obs, _, done, info = env.step(action)
        env.render()
        if done:
            obs = env.reset()
    env.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Processes agent parameters.')
    parser.add_argument('-r', '--render', action= 'store_true', help= 'Boolean flag for if the user wants the game environment to render during play')
    args = parser.parse_args()
    randomAgent = Agent()
    testMain(randomAgent, args.render)
