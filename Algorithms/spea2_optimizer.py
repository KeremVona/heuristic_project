import numpy as np
from pymoo.core.problem import Problem
from pymoo.core.sampling import Sampling
from pymoo.core.crossover import Crossover
from pymoo.core.mutation import Mutation
from pymoo.algorithms.moo.spea2 import SPEA2
from pymoo.optimize import minimize

from genetic import DietChromosome, GeneticOperators
from decoder import DietDecoder