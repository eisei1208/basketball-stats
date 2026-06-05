from flask import Flask, render_template, request, redirect, url_for, jsonify
from datetime import datetime
from models import db, Game, Quarter, QuarterStats, Setting, Appearance
from flask_migrate import Migrate

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///stats.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
migrate = Migrate(app, db)

with app.app_context():
    db.create_all()
    # 初期設定値の投入ロジックなどをここに記述

def calculate_summary(quarters):
    """Calculates summary for a list of quarters."""
    
    default_weights = {
        'w_3p_made': 3.0, 'w_2p_made': 2.0, 'w_ft_made': 1.0,
        'w_orb': 1.0, 'w_drb': 1.0, 'w_ast': 1.5, 'w_stl': 2.0,
        'w_blk': 2.0, 'w_fd': 1.0, 'w_pf': -1.5, 'w_to': -1.5, 'w_ft_miss': -1.0,
        'w_3p_miss': -1.0, 'w_2p_miss': -1.0,
        'w_ring_attack': 1.0, 'w_ft_drawn_bonus': 2.0, 'w_loose_ball_dive': 2.0,
        'w_gamemake_boost': 3.0, 'w_bench_datahack': 2.0, 'w_captain_boost': 2.0,
        'w_charge_drawn': 5.0
    }
    weights = default_weights.copy()
    for setting in Setting.query.all():
        if setting.key in weights:
            weights[setting.key] = setting.value

    stat_fields = [
        'fg3_made', 'fg3_miss', 'fg2_made', 'fg2_miss', 'ft_made', 'ft_miss',
        'orb', 'drb', 'ast', 'stl', 'blk', 'fd', 'pf', 'to',
        'ring_attack', 'ft_drawn_bonus', 'loose_ball_dive', 'gamemake_boost', 'bench_datahack', 'captain_boost', 'charge_drawn'
    ]
    summary = {field: 0 for field in stat_fields}
    summary['total_play_time_sec'] = 0

    # Ensure quarters is iterable (handle single object case)
    if not isinstance(quarters, (list, tuple)):
        quarters = [quarters]

    # 紐づいている試合情報を取得してレバレッジ（2倍ブースト）を適用
    game = None
    if len(quarters) > 0 and hasattr(quarters[0], 'game'):
        game = quarters[0].game
        
    if game and game.leverage_item:
        if game.leverage_item == 'pts':
            weights['w_3p_made'] *= 2
            weights['w_2p_made'] *= 2
            weights['w_ft_made'] *= 2
        elif game.leverage_item == 'drb':
            weights['w_drb'] *= 2
        elif game.leverage_item == 'orb':
            weights['w_orb'] *= 2
        elif game.leverage_item == 'ast':
            weights['w_ast'] *= 2
        elif game.leverage_item == 'stl':
            weights['w_stl'] *= 2
        elif game.leverage_item == 'blk':
            weights['w_blk'] *= 2
        elif game.leverage_item == 'ring_attack':
            weights['w_ring_attack'] *= 2
        elif game.leverage_item == 'ft_drawn_bonus':
            weights['w_ft_drawn_bonus'] *= 2
        elif game.leverage_item == 'loose_ball_dive':
            weights['w_loose_ball_dive'] *= 2
        elif game.leverage_item == 'gamemake_boost':
            weights['w_gamemake_boost'] *= 2
        elif game.leverage_item == 'bench_datahack':
            weights['w_bench_datahack'] *= 2
        elif game.leverage_item == 'captain_boost':
            weights['w_captain_boost'] *= 2
        elif game.leverage_item == 'charge_drawn':
            weights['w_charge_drawn'] *= 2

    for quarter in quarters:
        if quarter.stats:
            for field in stat_fields:
                val = getattr(quarter.stats, field)
                summary[field] += val if val is not None else 0
        
        for appearance in quarter.appearances:
            summary['total_play_time_sec'] += appearance.duration

    # Calculate derived values from the totals
    summary['total_score'] = (summary['fg3_made'] * 3) + (summary['fg2_made'] * 2) + (summary['ft_made'] * 1)
    summary['total_rebounds'] = summary['orb'] + summary['drb']
    
    # Calculate total evaluation
    evaluation = 0
    evaluation += summary.get('fg3_made', 0) * weights.get('w_3p_made', 0)
    evaluation += summary.get('fg2_made', 0) * weights.get('w_2p_made', 0)
    evaluation += summary.get('ft_made', 0) * weights.get('w_ft_made', 0)
    evaluation += summary.get('orb', 0) * weights.get('w_orb', 0)
    evaluation += summary.get('drb', 0) * weights.get('w_drb', 0)
    evaluation += summary.get('ast', 0) * weights.get('w_ast', 0)
    evaluation += summary.get('stl', 0) * weights.get('w_stl', 0)
    evaluation += summary.get('blk', 0) * weights.get('w_blk', 0)
    evaluation += summary.get('fd', 0) * weights.get('w_fd', 0)
    evaluation += summary.get('pf', 0) * weights.get('w_pf', 0)
    evaluation += summary.get('to', 0) * weights.get('w_to', 0)
    evaluation += summary.get('ft_miss', 0) * weights.get('w_ft_miss', 0)
    evaluation += summary.get('fg3_miss', 0) * weights.get('w_3p_miss', 0)
    evaluation += summary.get('fg2_miss', 0) * weights.get('w_2p_miss', 0)
    evaluation += summary.get('ring_attack', 0) * weights.get('w_ring_attack', 0)
    evaluation += summary.get('ft_drawn_bonus', 0) * weights.get('w_ft_drawn_bonus', 0)
    evaluation += summary.get('loose_ball_dive', 0) * weights.get('w_loose_ball_dive', 0)
    evaluation += summary.get('gamemake_boost', 0) * weights.get('w_gamemake_boost', 0)
    evaluation += summary.get('bench_datahack', 0) * weights.get('w_bench_datahack', 0)
    evaluation += summary.get('captain_boost', 0) * weights.get('w_captain_boost', 0)
    evaluation += summary.get('charge_drawn', 0) * weights.get('w_charge_drawn', 0)
    summary['total_evaluation'] = round(evaluation, 1)
    
    return summary

@app.route('/')
def index():
    games = Game.query.order_by(Game.date.desc()).all()
    
    evaluations = {}
    for game in games:
        summary = calculate_summary(game.quarters)
        evaluations[game.id] = summary['total_evaluation']
    return render_template('index.html', games=games, evaluations=evaluations)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    default_weights = {
        'w_3p_made': 3.0, 'w_2p_made': 2.0, 'w_ft_made': 1.0,
        'w_orb': 1.0, 'w_drb': 1.0, 'w_ast': 1.5, 'w_stl': 2.0,
        'w_blk': 2.0, 'w_fd': 1.0, 'w_pf': -1.5, 'w_to': -1.5, 'w_ft_miss': -1.0,
        'w_3p_miss': -1.0, 'w_2p_miss': -1.0,
        'w_ring_attack': 1.0, 'w_ft_drawn_bonus': 2.0, 'w_loose_ball_dive': 2.0,
        'w_gamemake_boost': 3.0, 'w_bench_datahack': 2.0, 'w_captain_boost': 2.0,
        'w_charge_drawn': 5.0
    }
    # 一般設定のデフォルト
    default_general = {
        'default_quarter_length': 10.0
    }
    
    all_defaults = default_weights.copy()
    all_defaults.update(default_general)

    if request.method == 'POST':
        for key in all_defaults.keys():
            val = request.form.get(key)
            if val is not None:
                try:
                    float_val = float(val)
                    setting = Setting.query.filter_by(key=key).first()
                    if not setting:
                        setting = Setting(key=key)
                        db.session.add(setting)
                    setting.value = float_val
                except ValueError:
                    pass
        db.session.commit()
        return redirect(url_for('index'))

    current_weights = all_defaults.copy()
    for s in Setting.query.all():
        if s.key in current_weights:
            current_weights[s.key] = s.value
    return render_template('settings.html', weights=current_weights)

@app.route('/game/new', methods=['GET', 'POST'])
def new_game():
    if request.method == 'POST':
        # フォームからデータ取得
        date_str = request.form.get('date')
        game_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.now().date()

        new_game = Game(
            opponent=request.form.get('opponent'),
            category=request.form.get('category'),
            location=request.form.get('location'),
            memo=request.form.get('memo'),
            date=game_date,
            leverage_item=request.form.get('leverage_item')
        )
        db.session.add(new_game)
        db.session.flush() # ID生成のためflush

        # 自動で1Q〜4Qを作成
        for i in range(1, 5):
            q = Quarter(game_id=new_game.id, quarter_no=i, length_sec=600) # ミニバス等は適宜変更
            db.session.add(q)
            # スタッツレコードも空で作っておく
            stats = QuarterStats(quarter=q)
            db.session.add(stats)
        
        db.session.commit()
        return redirect(url_for('game_detail', game_id=new_game.id))
    # GETリクエストの場合は、new_game.htmlをレンダリング
    return render_template('new_game.html', today=datetime.now().date())

@app.route('/game/<int:game_id>')
def game_detail(game_id):
    game = Game.query.get_or_404(game_id)
    # クオーター順にソートして渡す
    quarters = sorted(game.quarters, key=lambda x: x.quarter_no)
    game_summary = calculate_summary(quarters)
    quarter_summaries = {q.id: calculate_summary(q) for q in quarters}
    
    # 設定からデフォルト時間を取得
    setting = Setting.query.filter_by(key='default_quarter_length').first()
    default_min = int(setting.value) if setting else 10
    
    return render_template('game_detail.html', game=game, quarters=quarters, summary=game_summary, quarter_summaries=quarter_summaries, default_min=default_min)

# API: スタッツ更新 (AJAX用)
@app.route('/api/stats/update', methods=['POST'])
def update_stats():
    data = request.json
    stat_id = data.get('stat_id')
    field = data.get('field') # 例: 'fg3_made'
    delta = data.get('delta') # +1 or -1

    allowed_fields = [
        'fg3_made', 'fg3_miss', 'fg2_made', 'fg2_miss', 'ft_made', 'ft_miss',
        'orb', 'drb', 'ast', 'stl', 'blk', 'fd', 'pf', 'to',
        'ring_attack', 'ft_drawn_bonus', 'loose_ball_dive', 'gamemake_boost', 
        'bench_datahack', 'captain_boost', 'charge_drawn'
    ]
    if field not in allowed_fields:
        return jsonify({'success': False, 'message': 'Invalid field'}), 400

    stat_record = QuarterStats.query.get(stat_id)
    if stat_record:
        current_val = getattr(stat_record, field)
        new_val = max(0, (current_val if current_val is not None else 0) + delta) # 0未満防止
        setattr(stat_record, field, new_val)
        db.session.commit()
        
        # Calculate summaries
        game_summary = calculate_summary(stat_record.quarter.game.quarters)
        quarter_summary = calculate_summary(stat_record.quarter)
        
        return jsonify({'success': True, 'new_value': new_val, 
                        'summary': game_summary, 
                        'quarter_summary': quarter_summary, 'quarter_id': stat_record.quarter.id})
    return jsonify({'success': False}), 400

# API: OT追加
@app.route('/api/game/<int:game_id>/add_ot', methods=['POST'])
def add_ot(game_id):
    game = Game.query.get_or_404(game_id)
    max_q = max([q.quarter_no for q in game.quarters]) if game.quarters else 0
    new_q_no = max_q + 1
    
    # OTの長さ設定 (例: 300秒)
    ot_q = Quarter(game_id=game.id, quarter_no=new_q_no, length_sec=300)
    db.session.add(ot_q)
    stats = QuarterStats(quarter=ot_q)
    db.session.add(stats)
    db.session.commit()
    
    return jsonify({'success': True})

# API: 出場時間記録
@app.route('/api/appearance/add', methods=['POST'])
def add_appearance():
    data = request.json
    try:
        # バリデーション
        if not all(k in data for k in ['quarter_id', 'in_time_sec', 'out_time_sec']):
            return jsonify({'success': False, 'message': 'データが不足しています。'}), 400

        appearance = Appearance(
            quarter_id=data['quarter_id'],
            in_time_sec=data['in_time_sec'],
            out_time_sec=data['out_time_sec']
        )
        db.session.add(appearance)
        db.session.commit()
        
        # Calculate summaries
        game_summary = calculate_summary(appearance.quarter.game.quarters)
        quarter_summary = calculate_summary(appearance.quarter)

        # 成功レスポンスを返す
        return jsonify({'success': True, 'appearance_id': appearance.id, 
                        'summary': game_summary, 
                        'quarter_summary': quarter_summary, 'quarter_id': appearance.quarter.id})

    except Exception as e:
        db.session.rollback()
        print(f"Error: {e}") # サーバーログにエラーを出力
        return jsonify({'success': False, 'message': 'サーバーエラーが発生しました。'}), 500

# API: 試合削除
@app.route('/api/game/<int:game_id>', methods=['DELETE'])
def delete_game(game_id):
    try:
        game = Game.query.get_or_404(game_id)
        db.session.delete(game)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting game: {e}")
        return jsonify({'success': False, 'message': '削除中にエラーが発生しました。'}), 500

# API: 延長クオーター削除
@app.route('/api/quarter/<int:quarter_id>', methods=['DELETE'])
def delete_quarter(quarter_id):
    try:
        quarter = Quarter.query.get_or_404(quarter_id)
        
        # 1Q-4Qは削除させない
        if quarter.quarter_no <= 4:
            return jsonify({'success': False, 'message': '基本クオーターは削除できません。'}), 400

        db.session.delete(quarter)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting quarter: {e}")
        return jsonify({'success': False, 'message': '削除中にエラーが発生しました。'}), 500

# API: 出場記録削除
@app.route('/api/appearance/<int:appearance_id>', methods=['DELETE'])
def delete_appearance(appearance_id):
    try:
        appearance = Appearance.query.get_or_404(appearance_id)
        quarter = appearance.quarter
        game = quarter.game

        db.session.delete(appearance)
        db.session.commit()

        # 削除後にサマリーを再計算
        game_summary = calculate_summary(game.quarters)
        quarter_summary = calculate_summary(quarter)

        return jsonify({'success': True, 'summary': game_summary, 'quarter_summary': quarter_summary, 'quarter_id': quarter.id})
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting appearance: {e}")
        return jsonify({'success': False, 'message': '削除中にエラーが発生しました。'}), 500

# API: 試合情報更新
@app.route('/api/game/<int:game_id>/update', methods=['POST'])
def update_game(game_id):
    try:
        game = Game.query.get_or_404(game_id)
        data = request.json
        
        if 'opponent' in data:
            game.opponent = data['opponent']
        if 'category' in data:
            game.category = data['category']
        if 'date' in data and data['date']:
            game.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        if 'leverage_item' in data:
            game.leverage_item = data['leverage_item']
                
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error updating game: {e}")
        return jsonify({'success': False, 'message': '更新中にエラーが発生しました。'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)