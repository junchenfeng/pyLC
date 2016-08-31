import numpy as np
import ipdb
from tqdm import tqdm

from collections import defaultdict


# use EM to compute the bayes net
class BKT_HMM_EM(object):		
			
	def _load_observ(self, data):
		self.K = len(set([x[0] for x in data]))
		self.T = max([x[1] for x in data]) + 1
		
		self.observ_data = np.empty((self.T, self.K))
		T_array = np.zeros((self.K,))
		
		for log in data:
			i = log[0]; t = log[1]; y = log[2]
			self.observ_data[t, i] = y
			T_array[i] = t
		
		self.T_vec = [int(x)+1 for x in T_array.tolist()] 
		self.T = max(self.T_vec)
		
		# initilize for the rest of the structure
		st_size = (self.T, self.K, 2)
		self.a_vec = np.zeros(st_size)
		self.b_vec = np.zeros(st_size)
		
		self.r_vec = np.zeros(st_size)
		self.eta_vec = np.zeros((self.T, self.K, 2,2))
		self.r_vec_uncond = np.zeros(st_size)
		self.eta_vec_uncond  = np.zeros((self.T, self.K, 2,2))		
			
		# initialize
		self._update_derivative_parameter()  # learning spead
		
		
	def _update_derivative_parameter(self):
		self.state_transit_matrix = np.array([[1-self.l, self.l], [0, 1]])
		self.state_init_dist = np.array([1-self.pi, self.pi])
		self.observ_prob_matrix = np.array([[1-self.g, self.g], [self.s, 1-self.s]])  # index by state, observ

	def _update_forward(self, t, k, state):
		observ = int(self.observ_data[t,k])
		if t == 0:
			self.a_vec[t,k,state] = self.state_init_dist[state] * self.observ_prob_matrix[state, observ]
		else:
			self.a_vec[t,k,state] = np.dot(self.a_vec[t-1,k,:], self.state_transit_matrix[:,state]) * self.observ_prob_matrix[state, observ]
	
	def _update_backward(self, t, k, state):
		if t == self.T_vec[k]-1:
			self.b_vec[t,k,state] = 1
		else:
			observ = int(self.observ_data[t+1,k])
			if state == 0:
				self.b_vec[t,k,state] = self.state_transit_matrix[0,1]*self.observ_prob_matrix[1, observ]*self.b_vec[t+1,k,1] + self.state_transit_matrix[0,0]*self.observ_prob_matrix[0, observ]*self.b_vec[t+1,k,0]
			else:
				self.b_vec[t,k,state] = self.observ_prob_matrix[state, observ]*self.b_vec[t+1,k,1]

	def _update_eta(self, t, k):
		observ = int(self.observ_data[t+1,k])
		eta_raw = np.zeros((2,2))
		eta_raw[0,0] = self.a_vec[t,k,0]*self.state_transit_matrix[0,0]*self.observ_prob_matrix[0,observ]*self.b_vec[t+1,k,0]
		eta_raw[0,1] = self.a_vec[t,k,0]*self.state_transit_matrix[0,1]*self.observ_prob_matrix[1,observ]*self.b_vec[t+1,k,1]
		eta_raw[1,0] = self.a_vec[t,k,1]*self.state_transit_matrix[1,0]*self.observ_prob_matrix[0,observ]*self.b_vec[t+1,k,0]
		eta_raw[1,1] = self.a_vec[t,k,1]*self.state_transit_matrix[1,1]*self.observ_prob_matrix[1,observ]*self.b_vec[t+1,k,1]
		eta = eta_raw/eta_raw.sum()
		return eta, eta_raw
		
	def _update_gamma(self, t, k):
		gamma_raw = np.zeros((2,))
		gamma_raw[0] = self.a_vec[t,k,0]*self.b_vec[t,k,0]
		gamma_raw[1] = self.a_vec[t,k,1]*self.b_vec[t,k,1]
		gamma = gamma_raw/gamma_raw.sum()
		return gamma, gamma_raw
	
		
	def estimate(self, init_param, data, max_iter=10):
	
		self.g = init_param['g']  # guess
		self.s = init_param['s']  # slippage
		self.pi = init_param['pi']  # initial prob of mastery
		self.l = init_param['l']  # learn speed
		
		self.prior_param = {'l':[2,2],
							's':[1,2],
							'g':[1,2],
							'pi':[2,2]}	
		self._load_observ(data)
		
		#TODO: better convergence property
		for i in range(max_iter):
			self._em_update()
		
		return self.s, self.g, self.pi, self.l
			
	def _em_update(self):
		for k in range(self.K):
			# update forward
			for t in range(self.T_vec[k]):
				self._update_forward(t, k, 0)
				self._update_forward(t, k, 1)
				
			# update backward
			for t in range(self.T_vec[k]-1,-1,-1):
				self._update_backward(t, k, 0)
				self._update_backward(t, k, 1)
				
			# compute r
			for t in range(self.T_vec[k]):
				self.r_vec[t,k,:], self.r_vec_uncond[t,k,:] = self._update_gamma(t,k)

			# compute eta
			for t in range(self.T_vec[k]-1):
				self.eta_vec[t,k,:,:], self.eta_vec_uncond[t,k,:,:] = self._update_eta(t,k)
		
		# update parameters
		# obs_weight = np.ones((self.K,))
		obs_prob = np.empty((self.K,))
		for k in range(self.K):
			obs_prob[k] = self.a_vec[self.T_vec[k]-1,k,:].sum()
		obs_weight = 1/obs_prob
		
		#ipdb.set_trace()	
		self.pi = self.r_vec[0,:,1].mean()
		
		#denominator = np.dot((self.a_vec[0:t-1,:,0]*self.b_vec[0:t-1,:,0]).sum(axis=0), obs_weight) # sum(P(X^k_t=i|O^k))
		self.l = np.dot(self.eta_vec_uncond[:,:,0,1].sum(axis=0), obs_weight) / np.dot(self.r_vec_uncond[:,:,0].sum(axis=0), obs_weight)  # transit from 0 to 1
		
		# need to count the right and wrong
		self.tmp = np.zeros((self.T, self.K,2))
		for k in range(self.K):
			for t in range(self.T_vec[k]):
				observ = int(self.observ_data[t, k])
				self.tmp[t, k, observ] = self.r_vec_uncond[t, k, 1-observ]
		self.s = np.dot(self.tmp[:,:,0].sum(axis=0), obs_weight) / np.dot(self.r_vec_uncond[:,:,1].sum(axis=0), obs_weight) # observe 0 when state is 1
		self.g = np.dot(self.tmp[:,:,1].sum(axis=0), obs_weight) / np.dot(self.r_vec_uncond[:,:,0].sum(axis=0), obs_weight) # observe 1 when state is 0
		
		# update the derivatives
		self._update_derivative_parameter()

		

		
		
if __name__ == '__main__':	
	
	# unit test array
	init_param = {'s':0.1,
				  'g':0.2, 
				  'pi':0.6,
				  'l':0.3}
	
	data_array = [(0,0,0),(0,1,1)]
	
	x = BKT_HMM_EM(init_param)
	x.estimate(data_array, L=1)	

	print('a vec')
	print(x.a_vec)
	print(np.array([[0.32, 0.06],[0.0448, 0.1404]]))
	
	print('b vec')
	print(x.b_vec)
	print(np.array([[0.41, 0.9 ],[1,1]]))

	print('r vec')
	print(x.r_vec)
	print(np.array([[0.708,0.292],[0.242,0.758]]))

	print('eta vec')
	print(x.eta_vec[0])
	print(np.array([[0.242,0.467],[0,0.291]]))	
	


	
	