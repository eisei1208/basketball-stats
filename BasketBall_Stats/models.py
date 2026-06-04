from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=datetime.utcnow)
    opponent = db.Column(db.String(100))
    location = db.Column(db.String(100))
    category = db.Column(db.String(50)) # 練習/公式など
    memo = db.Column(db.Text)
    leverage_item = db.Column(db.String(50), nullable=True) # 勝負項目（レバレッジ）
    
    # リレーション: 試合削除時に紐づくQuarterも削除
    quarters = db.relationship('Quarter', backref='game', cascade="all, delete-orphan", lazy=True)

    @property
    def total_score(self):
        return sum(q.stats.total_score for q in self.quarters if q.stats)

    @property
    def leverage_item_name(self):
        mapping = {
            'pts': '得点 (PTS)',
            'drb': 'Dリバウンド (DRB)',
            'orb': 'Oリバウンド (ORB)',
            'ast': 'アシスト (AST)',
            'stl': 'スティール (STL)',
            'blk': 'ブロック (BLK)',
            'ring_attack': 'リングアタック',
            'ft_drawn_bonus': 'フリースロー(FT)獲得',
            'loose_ball_dive': 'ルーズボール・ダイブ',
            'gamemake_boost': 'ゲームメイク・ブースト',
            'bench_datahack': 'ベンチ・データハック',
            'captain_boost': 'キャプテン・ブースト',
            'charge_drawn': 'オフェンスチャージ獲得'
        }
        return mapping.get(self.leverage_item, '')

class Quarter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    quarter_no = db.Column(db.Integer, nullable=False) # 1, 2, 3, 4, 5(OT1)...
    length_sec = db.Column(db.Integer, default=600) # 10分=600秒
    
    # リレーション
    stats = db.relationship('QuarterStats', backref='quarter', uselist=False, cascade="all, delete-orphan")
    appearances = db.relationship('Appearance', backref='quarter', cascade="all, delete-orphan")

    @property
    def name(self):
        if self.quarter_no <= 4:
            return f"{self.quarter_no}Q"
        return f"OT{self.quarter_no - 4}"

class QuarterStats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quarter_id = db.Column(db.Integer, db.ForeignKey('quarter.id'), nullable=False)
    
    # 記録項目
    fg3_made = db.Column(db.Integer, default=0)
    fg3_miss = db.Column(db.Integer, default=0)
    fg2_made = db.Column(db.Integer, default=0)
    fg2_miss = db.Column(db.Integer, default=0)
    ft_made = db.Column(db.Integer, default=0)
    ft_miss = db.Column(db.Integer, default=0)
    orb = db.Column(db.Integer, default=0)
    drb = db.Column(db.Integer, default=0)
    ast = db.Column(db.Integer, default=0)
    stl = db.Column(db.Integer, default=0)
    blk = db.Column(db.Integer, default=0)
    fd = db.Column(db.Integer, default=0) # 被ファール
    pf = db.Column(db.Integer, default=0) # ファール
    to = db.Column(db.Integer, default=0) # ターンオーバー
    
    # 専用ボーナス
    ring_attack = db.Column(db.Integer, default=0)
    ft_drawn_bonus = db.Column(db.Integer, default=0)
    loose_ball_dive = db.Column(db.Integer, default=0)
    gamemake_boost = db.Column(db.Integer, default=0)
    bench_datahack = db.Column(db.Integer, default=0)
    captain_boost = db.Column(db.Integer, default=0)
    charge_drawn = db.Column(db.Integer, default=0)

    @property
    def total_score(self):
        return (self.fg3_made * 3) + (self.fg2_made * 2) + (self.ft_made * 1)

    @property
    def total_rebounds(self):
        return self.orb + self.drb

    def calculate_evaluation(self, weights):
        # weightsはSettingモデルから取得した辞書を想定
        score = 0
        score += self.fg3_made * weights.get('w_3p_made', 0)
        score += self.fg2_made * weights.get('w_2p_made', 0)
        score += self.ft_made * weights.get('w_ft_made', 0)
        score += self.orb * weights.get('w_orb', 0)
        score += self.drb * weights.get('w_drb', 0)
        score += self.ast * weights.get('w_ast', 0)
        score += self.stl * weights.get('w_stl', 0)
        score += self.blk * weights.get('w_blk', 0)
        score += self.fd * weights.get('w_fd', 0)
        # マイナス項目
        score += self.pf * weights.get('w_pf', 0) # 設定値自体を負にするか、ここで引くか統一が必要
        score += self.to * weights.get('w_to', 0)
        score += self.ft_miss * weights.get('w_ft_miss', 0)
        score += self.ring_attack * weights.get('w_ring_attack', 0)
        score += self.ft_drawn_bonus * weights.get('w_ft_drawn_bonus', 0)
        score += self.loose_ball_dive * weights.get('w_loose_ball_dive', 0)
        score += self.gamemake_boost * weights.get('w_gamemake_boost', 0)
        score += self.bench_datahack * weights.get('w_bench_datahack', 0)
        score += self.captain_boost * weights.get('w_captain_boost', 0)
        score += self.charge_drawn * weights.get('w_charge_drawn', 0)
        return score

class Appearance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quarter_id = db.Column(db.Integer, db.ForeignKey('quarter.id'), nullable=False)
    in_time_sec = db.Column(db.Integer) # 残り時間(秒)
    out_time_sec = db.Column(db.Integer) # 残り時間(秒)

    @property
    def duration(self):
        if self.in_time_sec is not None and self.out_time_sec is not None:
            return self.in_time_sec - self.out_time_sec
        return 0

class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True)
    value = db.Column(db.Float, default=1.0)
