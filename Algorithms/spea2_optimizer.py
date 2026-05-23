import numpy as np
from pymoo.core.problem import Problem
from pymoo.core.sampling import Sampling
from pymoo.core.crossover import Crossover
from pymoo.core.mutation import Mutation
from pymoo.algorithms.moo.spea2 import SPEA2
from pymoo.optimize import minimize

from genetic import DietChromosome, GeneticOperators
from decoder import DietDecoder

# ==========================================
# 1. PYMOO OPERATÖR ENTEGRASYONLARI
# ==========================================

class DietSampling(Sampling):
    """Başlangıç popülasyonunu oluşturur."""
    def __init__(self, breakfast_ids, lunch_dinner_ids):
        super().__init__()
        self.breakfast_ids = breakfast_ids
        self.lunch_dinner_ids = lunch_dinner_ids

    def _do(self, problem, n_samples, **kwargs):
        X = np.empty((n_samples, 1), dtype=object)
        for i in range(n_samples):
            X[i, 0] = DietChromosome(self.breakfast_ids, self.lunch_dinner_ids, randomize=True)
        return X

class DietCrossover(Crossover):
    """genetic.py içindeki Ordered Crossover işlemini pymoo'ya bağlar."""
    def __init__(self, prob=0.9):
        # DİKKAT: prob=prob argümanını super()'in içinden sildik.
        # Artık Pymoo bu değeri kendi objesine dönüştüremeyecek.
        super().__init__(2, 2) 
        
        # Olasılığı tamamen kendi kontrolümüze (saf float olarak) alıyoruz:
        self.crossover_prob = float(prob)

    def _do(self, problem, X, **kwargs):
        _, n_matings, _ = X.shape
        Y = np.empty_like(X)
        for i in range(n_matings):
            p1 = X[0, i, 0]
            p2 = X[1, i, 0]
            
            # Artık pymoo'nun Real objesiyle değil, kendi yarattığımız float değişkenle kıyaslıyoruz
            if np.random.random() < self.crossover_prob:
                b_c1, b_c2 = GeneticOperators.ordered_crossover(p1.breakfast_part, p2.breakfast_part)
                l_c1, l_c2 = GeneticOperators.ordered_crossover(p1.lunch_dinner_part, p2.lunch_dinner_part)
            else:
                b_c1, b_c2 = p1.breakfast_part[:], p2.breakfast_part[:]
                l_c1, l_c2 = p1.lunch_dinner_part[:], p2.lunch_dinner_part[:]
                
            Y[0, i, 0] = DietChromosome(b_c1, l_c1, randomize=False)
            Y[1, i, 0] = DietChromosome(b_c2, l_c2, randomize=False)
        return Y

class DietMutation(Mutation):
    """genetic.py içindeki Swap Mutation işlemini pymoo'ya bağlar."""
    def __init__(self):
        super().__init__()

    def _do(self, problem, X, **kwargs):
        for i in range(len(X)):
            chromo = X[i, 0]
            pm_b = 1.0 / len(chromo.breakfast_part) if chromo.breakfast_part else 0
            pm_l = 1.0 / len(chromo.lunch_dinner_part) if chromo.lunch_dinner_part else 0
            
            new_b = GeneticOperators.swap_mutation(chromo.breakfast_part, pm_b)
            new_l = GeneticOperators.swap_mutation(chromo.lunch_dinner_part, pm_l)
            X[i, 0] = DietChromosome(new_b, new_l, randomize=False)
        return X

# ==========================================
# 2. PROBLEM TANIMLAMASI
# ==========================================

class DietProblem(Problem):
    """Amaç fonksiyonlarının, cezaların ve kısıtların hesaplandığı sınıf."""
    def __init__(self, user, foods_dict, evaluator):
        # n_var=1 (Kromozom objesi), n_obj=3 (Pref, Cost, Time), n_ieq_constr=1 (Diversity)
        super().__init__(n_var=1, n_obj=3, n_ieq_constr=1)
        self.user = user
        self.foods = foods_dict
        self.evaluator = evaluator

    def _evaluate(self, X, out, *args, **kwargs):
        f1_pref = np.zeros(len(X))
        f2_cost = np.zeros(len(X))
        f3_time = np.zeros(len(X))
        g_div = np.zeros(len(X))

        for i in range(len(X)):
            chromosome = X[i, 0]
            
            # 1. Kromozomu Decode Et
            b_menu, ld_menu, totals = DietDecoder.decode(chromosome, self.user, self.foods)
            full_menu = b_menu + ld_menu
            
            # 2. DRI Cezasını Hesapla (R)
            R = self.evaluator.calculate_penalty(totals, self.user.dri_limits)
            
            # 3. Ham Amaç Değerlerini Hesapla
            pref_score = sum(self.foods[f_id].preference for f_id in full_menu)
            cost_score = sum(self.foods[f_id].cost for f_id in full_menu)
            time_score = sum((self.foods[f_id].prep_time + self.foods[f_id].cook_time) for f_id in full_menu)
            
            # 4. Fitness = Objective + Penalty
            # Not: Pymoo her şeyi MINIMIZE eder.
            # - Preference maksimize edilmek istendiği için negatifini alıyoruz.
            # - Ceza puanı algoritmada kötüleşmeye sebep olmalı, bu yüzden + (lambda * R) ekliyoruz.
            lambda_w = self.evaluator.lambda_weight
            
            f1_pref[i] = -pref_score + (lambda_w * R)
            f2_cost[i] = cost_score + (lambda_w * R)
            f3_time[i] = time_score + (lambda_w * R)
            
            # 5. Diversity (Option C) Kısıtı: Distinct Food Groups >= 4
            groups = set(self.foods[f_id].food_group_id for f_id in full_menu)
            
            # Pymoo'da kısıtlar G <= 0 şeklinde çalışır.
            # Eğer (4 - len(groups)) <= 0 ise kurala uyuyor demektir. Sıfırdan büyükse elenir.
            g_div[i] = 4 - len(groups)
            
        out["F"] = np.column_stack([f1_pref, f2_cost, f3_time])
        out["G"] = g_div

# ==========================================
# 3. ÇALIŞTIRICI FONKSİYON
# ==========================================

def run_spea2(user, user_foods, evaluator, pop_size=50, n_gen=100):
    """Belirtilen kullanıcı için SPEA2 algoritmasını başlatır."""
    
    # Tüm ID'leri al ve kahvaltı / öğle-akşam olarak ikiye böl (Handout: 94 ve 311)
    all_food_ids = list(user_foods.keys())
    breakfast_ids = all_food_ids[:94]
    lunch_dinner_ids = all_food_ids[94:]
    
    # Problemi ve Operatörleri Tanımla
    problem = DietProblem(user, user_foods, evaluator)
    
    algorithm = SPEA2(
        pop_size=pop_size,
        sampling=DietSampling(breakfast_ids, lunch_dinner_ids),
        crossover=DietCrossover(prob=0.9),
        mutation=DietMutation(),
        eliminate_duplicates=False # Custom obje kullandığımız için false yapıyoruz
    )
    
    print(f"\n🚀 SPEA2 başlatılıyor... (Kullanıcı {user.user_id} - Popülasyon: {pop_size}, Jenerasyon: {n_gen})")
    
    res = minimize(
        problem,
        algorithm,
        ('n_gen', n_gen),
        seed=42,
        verbose=True
    )
    
    return res