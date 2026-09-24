import logging
import re
from difflib import SequenceMatcher
from package.models.evaluation import PropertyEvaluation
from package.utils.url_matcher import UrlMatcher
logger = logging.getLogger(__name__)

def normalize_address(address: str) -> str:
    """
    住所の表記揺れを最小限にするための正規化関数。
    - 全角英数字・記号を半角に変換
    - 漢数字をアラビア数字に変換
    - 「丁目」「番」「号」「番地」等をハイフンに統一
    - スペースの排除
    """
    if not address:
        return ''
    address = address.translate(str.maketrans('０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ', '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'))
    address = re.sub('[\\s\u3000]+', '', address)
    address = re.sub('[－ー‐—―〜~−]+', '-', address)
    kanji_digits = {'一': '1', '二': '2', '三': '3', '四': '4', '五': '5', '六': '6', '七': '7', '八': '8', '九': '9', '十': '10'}
    for k, v in kanji_digits.items():
        address = address.replace(k, v)
    address = re.sub('(\\d+)丁目', '\\1-', address)
    address = re.sub('(\\d+)番(?:地|の)?', '\\1-', address)
    address = re.sub('(\\d+)号', '\\1', address)
    address = re.sub('-+', '-', address)
    address = address.strip('-')
    return address
COMPANIES = ['mitsui', 'sumifu', 'tokyu', 'nomura', 'misawa', 'smtrc', 'sumai1', 'mizuho', 'odakyu', 'afr', 'sekisui', 'daiwa', 'totate', 'athome', 'homes', 'seibu', 'keikyu', 'sotetsu', 'keisei', 'daikyo', 'rearie', 'heim', 'sumirin', 'keio']

def _get_real_property(eval_rec: PropertyEvaluation):
    """評価レコードに紐づく物件実データをモデルから解決する"""
    try:
        from django.apps import apps
        company = eval_rec.company
        ptype = eval_rec.property_type
        if company == 'unknown':
            for c in COMPANIES:
                if ptype.lower().startswith(c):
                    company = c
                    ptype = ptype.lower().replace(c, '')
                    break
        company_camel = company.capitalize()
        ptype_camel = ptype.replace('apartment', 'Apartment').replace('kodate', 'Kodate').replace('mansion', 'Mansion').replace('tochi', 'Tochi').replace('investment', 'Investment')
        if ptype_camel:
            ptype_camel = ptype_camel[0].upper() + ptype_camel[1:]
        model_name = f'{company_camel}{ptype_camel}'
        model_class = apps.get_model('package', model_name)
        return model_class.objects.filter(id=eval_rec.property_id).first()
    except Exception as e:
        logger.warning(f'Failed to load real property data for evaluation {eval_rec.id}: {e}')
        return None

def _calculate_address_score(prop_a, prop_b) -> float:
    addr_a = normalize_address(getattr(prop_a, 'address', ''))
    addr_b = normalize_address(getattr(prop_b, 'address', ''))
    if not addr_a or not addr_b:
        return 0.0
    if addr_a == addr_b:
        return 0.50

    match_ratio = SequenceMatcher(None, addr_a, addr_b).ratio()
    if match_ratio >= 0.85:
        return 0.35
    if match_ratio >= 0.7:
        return 0.2
    return 0.0

def _calculate_area_score(prop_a, prop_b) -> float:
    area_a = float(getattr(prop_a, 'tatemonoMenseki', 0) or getattr(prop_a, 'senyuMenseki', 0) or 0)
    area_b = float(getattr(prop_b, 'tatemonoMenseki', 0) or getattr(prop_b, 'senyuMenseki', 0) or 0)
    if area_a <= 0 or area_b <= 0:
        return 0.0
    diff_ratio = abs(area_a - area_b) / max(area_a, area_b)
    if diff_ratio <= 0.01:
        return 0.3
    if diff_ratio <= 0.03:
        return 0.2
    if diff_ratio <= 0.07:
        return 0.1
    return 0.0

def _calculate_price_score(prop_a, prop_b) -> float:
    price_a = float(prop_a.price if prop_a.price else 0)
    price_b = float(prop_b.price if prop_b.price else 0)
    if price_a <= 0 or price_b <= 0:
        return 0.0
    diff_ratio = abs(price_a - price_b) / max(price_a, price_b)
    if diff_ratio <= 0.01:
        return 0.2
    if diff_ratio <= 0.03:
        return 0.15
    if diff_ratio <= 0.07:
        return 0.1
    if diff_ratio <= 0.15:
        return 0.05
    return 0.0

def _calculate_date_score(prop_a, prop_b) -> float:
    date_a = getattr(prop_a, 'chikunengetsu', None)
    date_b = getattr(prop_b, 'chikunengetsu', None)
    if date_a and date_b and (date_a == date_b):
        return 0.1
    str_a = getattr(prop_a, 'chikunengetsuStr', '')
    str_b = getattr(prop_b, 'chikunengetsuStr', '')
    if str_a and str_b and (str_a == str_b):
        return 0.1
    return 0.0

def calculate_property_similarity(eval_a: PropertyEvaluation, eval_b: PropertyEvaluation, prop_a=None, prop_b=None) -> float:
    """
    2つの PropertyEvaluation レコード（および紐づく実データ）の類似度を計算する。
    戻り値: 0.0 (全く異なる) 〜 1.0 (完全に同一) の類似度スコア
    """
    if UrlMatcher.is_same_url(eval_a.property_url, eval_b.property_url):
        return 1.0
    group_a = 'building' if eval_a.property_type in ['mansion', 'investmentapartment', 'tochi'] else 'house'
    group_b = 'building' if eval_b.property_type in ['mansion', 'investmentapartment', 'tochi'] else 'house'
    if group_a != group_b:
        return 0.0
    prop_a = prop_a if prop_a is not None else _get_real_property(eval_a)
    prop_b = prop_b if prop_b is not None else _get_real_property(eval_b)
    if not prop_a or not prop_b:
        return 0.0
    return _calculate_address_score(prop_a, prop_b) + _calculate_area_score(prop_a, prop_b) + _calculate_price_score(prop_a, prop_b) + _calculate_date_score(prop_a, prop_b)

def get_root_parent(eval_rec: PropertyEvaluation) -> PropertyEvaluation:
    """
    再帰的に duplicate_of を辿り、最上位の親レコード（ルート親）を取得する。
    万一循環参照が存在する場合でも無限ループを防止し、最もIDが小さいレコードを返却する。
    """
    if not eval_rec or not eval_rec.duplicate_of_id:
        return eval_rec
    curr = eval_rec
    visited_ids = set()
    best = curr
    while curr and curr.duplicate_of_id:
        if curr.id in visited_ids:
            break
        visited_ids.add(curr.id)
        parent = curr.duplicate_of
        if not parent:
            break
        curr = parent
        if curr.id is not None and (best.id is None or curr.id < best.id):
            best = curr
    return best if best.duplicate_of_id is None else curr

def find_duplicate_property(new_eval: PropertyEvaluation, new_prop=None) -> PropertyEvaluation | None:
    """
    新しく登録された PropertyEvaluation に対して、DB内に同一とみなせる類似物件レコードが存在するか検索する。
    - 登録日時が若いもの（PropertyEvaluation.id が小さい方）を常に親とし、大きい方を子とする。
    - 既に子であるレコードはルート親へ解消して直結（Flattening）し、多段チェーンおよび循環参照を防止する。
    """
    qs = PropertyEvaluation.objects.filter(property_type=new_eval.property_type)
    if new_eval.id is not None:
        qs = qs.filter(id__lt=new_eval.id)
    candidates = qs.order_by('-id')[:50]
    for cand in candidates:
        root = get_root_parent(cand)
        if new_eval.id is not None and (root.id == new_eval.id or root.id >= new_eval.id):
            continue
        similarity = calculate_property_similarity(new_eval, cand, prop_a=new_prop)
        if similarity >= 0.85:
            logger.info(f'Duplicate property detected: {new_eval.property_url} is duplicate of {root.property_url} (matched via {cand.property_url}, Similarity: {similarity:.2f})')
            return root
    return None