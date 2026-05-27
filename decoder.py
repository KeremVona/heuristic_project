from typing import List, Tuple, Dict, Any

class DietDecoder:
    """Kromozomdaki genleri (ID'leri) kurallara göre gerçek bir menüye dönüştürür.
    
    Permütasyon dizilerini (kahvaltı ve öğle/akşam) alır ve kısıtları 
    (vejetaryenlik, günlük limitler, kahvaltı hedefleri) sağlayacak şekilde
    öğünlere besinleri atar.
    """
    
    BREAKFAST_SPLIT = 0.35  # Kahvaltının günlük kalorideki tahmini payı
    TOLERANCE_UPPER = 1.15  # Üst limit toleransı
    TOLERANCE_LOWER = 0.90  # Alt hedef toleransı
    
    @classmethod
    def decode(cls, chromosome, user, foods_dict: Dict[int, Any]) -> Tuple[List[int], List[int], Dict[str, float]]:
        """Kromozomu çözer ve öğünlere ayrılmış menüyü oluşturur."""
        breakfast_menu = []
        lunch_dinner_menu = []
        
        # Güncel besin değerleri toplamını tutacak sözlük
        totals = {n: 0.0 for n in user.dri_limits.keys()}
        
        # --- LİMİTLERİN HESAPLANMASI ---
        # Kahvaltı için ulaşılmak istenen minimum hedefler (sadece Enerji ve Protein için)
        targets_b = {n: user.dri_limits[n][0] * cls.BREAKFAST_SPLIT * cls.TOLERANCE_LOWER 
                     for n in ['Energy', 'Protein'] if n in user.dri_limits}
        
        # Kahvaltı menüsü oluşturulurken Enerji ve Protein için aşılmaması gereken özel limit
        limits_b = {n: user.dri_limits[n][1] * cls.BREAKFAST_SPLIT * cls.TOLERANCE_UPPER 
                    for n in ['Energy', 'Protein'] if n in user.dri_limits}

        # Tüm gün için kesinlikle aşılmaması gereken genel üst limitler (Tüm besinler için)
        limits_daily = {n: user.dri_limits[n][1] * cls.TOLERANCE_UPPER for n in totals}
        
        # Tüm gün için ulaşılması hedeflenen minimum hedefler (Tüm besinler için)
        targets_daily = {n: user.dri_limits[n][0] * cls.TOLERANCE_LOWER for n in totals}

        # --- 1. KAHVALTI AŞAMASI ---
        for f_id in chromosome.breakfast_part:
            food = foods_dict.get(f_id)
            if not food: continue
            
            # Vejetaryen kısıtı
            if user.is_vegetarian and not food.is_vegetarian: 
                continue
            
            can_add = True
            
            # 1.a) Kahvaltıya özel üst limit kontrolü (Enerji ve Protein çok dolmasın)
            for n in ['Energy', 'Protein']:
                if n in food.nutrients and n in limits_b:
                    if totals.get(n, 0) + food.nutrients[n] > limits_b[n]:
                        can_add = False
                        break
            
            # 1.b) GÜNLÜK üst limit kontrolü (Örn: Kahvaltıda günlük sodyum sınırını aşmamak için)
            if can_add:
                for n, limit_val in limits_daily.items():
                    if n in food.nutrients:
                        if totals.get(n, 0) + food.nutrients[n] > limit_val:
                            can_add = False
                            break
            
            # Eğer tüm limitleri sağlıyorsa menüye ekle ve toplamları güncelle
            if can_add:
                breakfast_menu.append(f_id)
                for n, val in food.nutrients.items():
                    if n in totals: 
                        totals[n] += val
                        
            # Kahvaltı hedeflerine (Enerji/Protein %35) ulaşıldıysa kahvaltı seçimini bitir
            if targets_b and all(totals.get(n, 0) >= targets_b[n] for n in targets_b): 
                break

        # --- 2. ÖĞLE + AKŞAM AŞAMASI ---
        for f_id in chromosome.lunch_dinner_part:
            food = foods_dict.get(f_id)
            if not food: continue
            
            if user.is_vegetarian and not food.is_vegetarian: 
                continue
            
            can_add = True
            
            # Günlük genel üst limit kontrolü
            for n, limit_val in limits_daily.items():
                if n in food.nutrients:
                    if totals.get(n, 0) + food.nutrients[n] > limit_val:
                        can_add = False
                        break
            
            if can_add:
                lunch_dinner_menu.append(f_id)
                for n, val in food.nutrients.items():
                    if n in totals: 
                        totals[n] += val
                        
            # Tüm günlük minimum hedeflere ulaşıldıysa menüye eklemeyi durdur
            if targets_daily and all(totals.get(n, 0) >= targets_daily[n] for n in targets_daily): 
                break
                
        # Güvenlik: Boş menü durumunda en az bir bilgi döndür
        if not breakfast_menu and not lunch_dinner_menu:
            # Menü oluşturulamadı — tüm besinler sıfır
            pass  # Totals zaten sıfır, penalty yüksek olacak
            
        return breakfast_menu, lunch_dinner_menu, totals
