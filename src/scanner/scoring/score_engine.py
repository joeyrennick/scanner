def calculate_score(price, ma20, ma50, ma200, relative_strength):
    score = 0
    if price > ma20:
        score += 10
    if price > ma50:
        score += 15
    if price > ma200:
        score += 20
    if ma50 > ma200:
        score += 20
    if abs(price - ma20) / ma20 <= 0.05:
        score += 15
    if relative_strength > 0:
        score += 20
    return score
