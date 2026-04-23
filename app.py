from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime
from collections import defaultdict
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = "mysecretkey123"

database_url = os.environ.get("DATABASE_URL")
print("DATABASE_URL:", database_url)
if not database_url:
    raise RuntimeError("DATABASE_URL not set!")

database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ── LOGIN ──────────────────────────────────────────────────────────────────────
USERNAME = "admin"
PASSWORD = "0011"

# ── MODELS ────────────────────────────────────────────────────────────────────

class FixedCost(db.Model):
    __tablename__ = "fixed_costs"
    id         = db.Column(db.Integer, primary_key=True)
    rent       = db.Column(db.Float, default=0)
    eb         = db.Column(db.Float, default=0)
    gas        = db.Column(db.Float, default=0)
    wifi       = db.Column(db.Float, default=0)

    @property
    def total(self):
        return (self.rent or 0) + (self.eb or 0) + (self.gas or 0) + (self.wifi or 0)


class VariableCost(db.Model):
    __tablename__ = "variable_costs"
    id         = db.Column(db.Integer, primary_key=True)
    date       = db.Column(db.Date)
    provisions = db.Column(db.Float, default=0)
    vegetables = db.Column(db.Float, default=0)
    fruits     = db.Column(db.Float, default=0)
    meat_egg   = db.Column(db.Float, default=0)
    water      = db.Column(db.Float, default=0)
    transport  = db.Column(db.Float, default=0)
    others     = db.Column(db.Float, default=0)

    @property
    def total(self):
        return ((self.provisions or 0) + (self.vegetables or 0) + (self.fruits or 0) +
                (self.meat_egg or 0)   + (self.water or 0)      + (self.transport or 0) +
                (self.others or 0))


class ElectricityBoard(db.Model):
    __tablename__ = "electricity_board"
    id            = db.Column(db.Integer, primary_key=True)
    date          = db.Column(db.Date)
    meter_reading = db.Column(db.Float, default=0)
    daily_units   = db.Column(db.Float, default=0)
    total_units   = db.Column(db.Float, default=0)
    slab_rate     = db.Column(db.Float, default=0)
    daily_cost    = db.Column(db.Float, default=0)
    total_cost    = db.Column(db.Float, default=0)


class ExpenseDetails(db.Model):
    __tablename__ = "expense_details"
    id               = db.Column(db.Integer, primary_key=True)
    date             = db.Column(db.Date)
    provisions       = db.Column(db.String, default='')
    provisions_cost  = db.Column(db.Float, default=0)
    vegetables       = db.Column(db.String, default='')
    vegetables_cost  = db.Column(db.Float, default=0)
    fruits           = db.Column(db.String, default='')
    fruits_cost      = db.Column(db.Float, default=0)
    meat_egg         = db.Column(db.String, default='')
    meat_egg_cost    = db.Column(db.Float, default=0)
    water            = db.Column(db.Float, default=0)
    water_cost       = db.Column(db.Float, default=0)
    transport        = db.Column(db.String, default='')
    transport_cost   = db.Column(db.Float, default=0)
    others           = db.Column(db.String, default='')
    others_cost      = db.Column(db.Float, default=0)

    @property
    def total(self):
        return ((self.provisions_cost or 0) + (self.vegetables_cost or 0) +
                (self.fruits_cost or 0)     + (self.meat_egg_cost or 0)   +
                (self.water_cost or 0)      + (self.transport_cost or 0)  +
                (self.others_cost or 0))


with app.app_context():
    db.create_all()

# ── HELPERS ───────────────────────────────────────────────────────────────────

def login_required():
    return 'user' not in session

def parse_float(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default

def parse_date(val):
    try:
        return datetime.strptime(val, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return date.today()

# ── AUTH ──────────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['username'] == USERNAME and request.form['password'] == PASSWORD:
            session['user'] = request.form['username']
            return redirect(url_for('index'))
        error = "தவறான username அல்லது password!"
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if login_required():
        return redirect(url_for('login'))

    fixed    = FixedCost.query.first()
    variable = VariableCost.query.order_by(VariableCost.date.asc()).all()
    details  = ExpenseDetails.query.order_by(ExpenseDetails.date.asc()).all()
    eb_data  = ElectricityBoard.query.order_by(ElectricityBoard.date.asc()).all()

    fixed_total    = round(fixed.total if fixed else 0, 2)
    variable_total = round(sum(v.total for v in variable), 2)
    overall_total  = round(fixed_total + variable_total, 2)

    # pie chart
    pie_labels = ['Rent', 'Electricity', 'Gas', 'WiFi']
    pie_data   = [fixed.rent or 0, fixed.eb or 0, fixed.gas or 0, fixed.wifi or 0] if fixed else [0,0,0,0]

    # bar chart
    bar_labels = ['Provisions', 'Vegetables', 'Fruits', 'Meat & Eggs', 'Water', 'Transport', 'Others']
    bar_data   = [
        round(sum(v.provisions or 0 for v in variable), 2),
        round(sum(v.vegetables or 0 for v in variable), 2),
        round(sum(v.fruits     or 0 for v in variable), 2),
        round(sum(v.meat_egg   or 0 for v in variable), 2),
        round(sum(v.water      or 0 for v in variable), 2),
        round(sum(v.transport  or 0 for v in variable), 2),
        round(sum(v.others     or 0 for v in variable), 2),
    ]

    # line chart
    date_totals = defaultdict(float)
    for v in variable:
        if v.date:
            date_totals[v.date] += v.total
    sorted_dates = sorted(date_totals.keys())
    line_labels  = [d.strftime('%d %b') for d in sorted_dates]
    line_data    = [round(date_totals[d], 2) for d in sorted_dates]

    # EB chart
    eb_dates      = [e.date.strftime('%d %b') for e in eb_data if e.date]
    eb_daily      = [round(e.daily_cost  or 0, 2) for e in eb_data]
    eb_cumulative = [round(e.total_cost  or 0, 2) for e in eb_data]

    # details column totals
    dct = {
        'provisions' : round(sum(d.provisions_cost  or 0 for d in details), 2),
        'vegetables' : round(sum(d.vegetables_cost  or 0 for d in details), 2),
        'fruits'     : round(sum(d.fruits_cost       or 0 for d in details), 2),
        'meat_egg'   : round(sum(d.meat_egg_cost     or 0 for d in details), 2),
        'water'      : round(sum(d.water_cost        or 0 for d in details), 2),
        'transport'  : round(sum(d.transport_cost    or 0 for d in details), 2),
        'others'     : round(sum(d.others_cost       or 0 for d in details), 2),
    }
    dct['grand'] = round(sum(dct.values()), 2)

    today_str = date.today().strftime('%Y-%m-%d')

    return render_template('dashboard.html',
        fixed=fixed, fixed_total=fixed_total,
        variable_total=variable_total, overall_total=overall_total,
        pie_labels=pie_labels, pie_data=pie_data,
        bar_labels=bar_labels, bar_data=bar_data,
        line_labels=line_labels, line_data=line_data,
        eb_dates=eb_dates, eb_daily=eb_daily, eb_cumulative=eb_cumulative,
        details=details, dct=dct, eb_data=eb_data,
        today=today_str
    )


# ── ALL DATA ──────────────────────────────────────────────────────────────────

@app.route('/data')
def view_data():
    if login_required():
        return redirect(url_for('login'))
    fixed    = FixedCost.query.all()
    variable = VariableCost.query.order_by(VariableCost.date.desc()).all()
    details  = ExpenseDetails.query.order_by(ExpenseDetails.date.desc()).all()
    eb       = ElectricityBoard.query.order_by(ElectricityBoard.date.desc()).all()
    return render_template('data.html', fixed=fixed, variable=variable, details=details, eb=eb)


# ── ADD FIXED ─────────────────────────────────────────────────────────────────

@app.route('/add_fixed', methods=['GET', 'POST'])
def add_fixed():
    if login_required():
        return redirect(url_for('login'))
    fixed = FixedCost.query.first()
    if request.method == 'POST':
        if fixed:
            fixed.rent = parse_float(request.form.get('rent'))
            fixed.gas  = parse_float(request.form.get('gas'))
            fixed.wifi = parse_float(request.form.get('wifi'))
        else:
            fixed = FixedCost(
                rent=parse_float(request.form.get('rent')),
                eb=0,
                gas=parse_float(request.form.get('gas')),
                wifi=parse_float(request.form.get('wifi'))
            )
            db.session.add(fixed)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('add_fixed.html', fixed=fixed)


# ── ADD VARIABLE ──────────────────────────────────────────────────────────────

@app.route('/add_variable', methods=['GET', 'POST'])
def add_variable():
    if login_required():
        return redirect(url_for('login'))
    if request.method == 'POST':
        db.session.add(VariableCost(
            date       = parse_date(request.form.get('entry_date')),
            provisions = parse_float(request.form.get('provisions')),
            vegetables = parse_float(request.form.get('vegetables')),
            fruits     = parse_float(request.form.get('fruits')),
            meat_egg   = parse_float(request.form.get('meat_egg')),
            water      = parse_float(request.form.get('water')),
            transport  = parse_float(request.form.get('transport')),
            others     = parse_float(request.form.get('others')),
        ))
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('add_variable.html', today=date.today().strftime('%Y-%m-%d'))


# ── ADD EB ────────────────────────────────────────────────────────────────────

@app.route('/add_eb', methods=['GET', 'POST'])
def add_eb():
    if login_required():
        return redirect(url_for('login'))
    last = ElectricityBoard.query.order_by(ElectricityBoard.id.desc()).first()
    if request.method == 'POST':
        reading   = parse_float(request.form.get('meter_reading'))
        slab_rate = parse_float(request.form.get('slab_rate'))
        entry_date = parse_date(request.form.get('entry_date'))

        if last:
            daily_units = round(reading - last.meter_reading, 4)
            total_units = round((last.total_units or 0) + daily_units, 4)
            total_cost  = round((last.total_cost  or 0) + daily_units * slab_rate, 4)
        else:
            daily_units = 0.0
            total_units = 0.0
            total_cost  = 0.0

        daily_cost = round(daily_units * slab_rate, 4)

        db.session.add(ElectricityBoard(
            date=entry_date, meter_reading=reading,
            daily_units=daily_units, total_units=total_units,
            slab_rate=slab_rate, daily_cost=daily_cost, total_cost=total_cost
        ))

        # auto-update fixed EB
        fixed = FixedCost.query.first()
        if fixed:
            fixed.eb = total_cost
        else:
            db.session.add(FixedCost(eb=total_cost))

        db.session.commit()
        return redirect(url_for('index'))
    return render_template('add_eb.html', last=last, today=date.today().strftime('%Y-%m-%d'))


# ── ADD DETAILS ───────────────────────────────────────────────────────────────

@app.route('/add_details', methods=['GET', 'POST'])
def add_details():
    if login_required():
        return redirect(url_for('login'))
    if request.method == 'POST':
        db.session.add(ExpenseDetails(
            date            = parse_date(request.form.get('entry_date')),
            provisions      = request.form.get('provisions', ''),
            provisions_cost = parse_float(request.form.get('provisions_cost')),
            vegetables      = request.form.get('vegetables', ''),
            vegetables_cost = parse_float(request.form.get('vegetables_cost')),
            fruits          = request.form.get('fruits', ''),
            fruits_cost     = parse_float(request.form.get('fruits_cost')),
            meat_egg        = request.form.get('meat_egg', ''),
            meat_egg_cost   = parse_float(request.form.get('meat_egg_cost')),
            water           = parse_float(request.form.get('water')),
            water_cost      = parse_float(request.form.get('water_cost')),
            transport       = request.form.get('transport', ''),
            transport_cost  = parse_float(request.form.get('transport_cost')),
            others          = request.form.get('others', ''),
            others_cost     = parse_float(request.form.get('others_cost')),
        ))
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('add_details.html', today=date.today().strftime('%Y-%m-%d'))


# ── EDIT ──────────────────────────────────────────────────────────────────────

@app.route('/edit_fixed/<int:id>', methods=['GET', 'POST'])
def edit_fixed(id):
    if login_required():
        return redirect(url_for('login'))
    data = FixedCost.query.get_or_404(id)
    if request.method == 'POST':
        data.rent = parse_float(request.form.get('rent'))
        data.eb   = parse_float(request.form.get('eb'))
        data.gas  = parse_float(request.form.get('gas'))
        data.wifi = parse_float(request.form.get('wifi'))
        db.session.commit()
        return redirect(url_for('view_data'))
    return render_template('edit_fixed.html', fixed=data)


@app.route('/edit_variable/<int:id>', methods=['GET', 'POST'])
def edit_variable(id):
    if login_required():
        return redirect(url_for('login'))
    data = VariableCost.query.get_or_404(id)
    if request.method == 'POST':
        data.provisions = parse_float(request.form.get('provisions'))
        data.vegetables = parse_float(request.form.get('vegetables'))
        data.fruits     = parse_float(request.form.get('fruits'))
        data.meat_egg   = parse_float(request.form.get('meat_egg'))
        data.water      = parse_float(request.form.get('water'))
        data.transport  = parse_float(request.form.get('transport'))
        data.others     = parse_float(request.form.get('others'))
        db.session.commit()
        return redirect(url_for('view_data'))
    return render_template('edit_variable.html', v=data)


# ── DELETE ────────────────────────────────────────────────────────────────────

@app.route('/delete_fixed/<int:id>')
def delete_fixed(id):
    if login_required(): return redirect(url_for('login'))
    db.session.delete(FixedCost.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('view_data'))

@app.route('/delete_variable/<int:id>')
def delete_variable(id):
    if login_required(): return redirect(url_for('login'))
    db.session.delete(VariableCost.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('view_data'))

@app.route('/delete_eb/<int:id>')
def delete_eb(id):
    if login_required(): return redirect(url_for('login'))
    db.session.delete(ElectricityBoard.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('view_data'))

@app.route('/delete_details/<int:id>')
def delete_details(id):
    if login_required(): return redirect(url_for('login'))
    db.session.delete(ExpenseDetails.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('view_data'))


# ── API: DATE FILTER ──────────────────────────────────────────────────────────

@app.route('/get-expenses')
def get_expenses():
    if login_required():
        return jsonify({"error": "Unauthorized"}), 401

    start_str = request.args.get('start_date')
    end_str   = request.args.get('end_date')

    query = VariableCost.query
    if start_str and end_str:
        start = parse_date(start_str)
        end   = parse_date(end_str)
        query = query.filter(VariableCost.date.between(start, end))

    variable = query.all()
    fixed    = FixedCost.query.first()

    fixed_total    = round(fixed.total if fixed else 0, 2)
    variable_total = round(sum(v.total for v in variable), 2)
    overall_total  = round(fixed_total + variable_total, 2)

    bar_data = [
        round(sum(v.provisions or 0 for v in variable), 2),
        round(sum(v.vegetables or 0 for v in variable), 2),
        round(sum(v.fruits     or 0 for v in variable), 2),
        round(sum(v.meat_egg   or 0 for v in variable), 2),
        round(sum(v.water      or 0 for v in variable), 2),
        round(sum(v.transport  or 0 for v in variable), 2),
        round(sum(v.others     or 0 for v in variable), 2),
    ]

    date_totals = defaultdict(float)
    for v in variable:
        if v.date:
            date_totals[v.date] += v.total
    sorted_dates = sorted(date_totals.keys())
    line_labels  = [d.strftime('%d %b') for d in sorted_dates]
    line_data    = [round(date_totals[d], 2) for d in sorted_dates]

    return jsonify({
        "fixed_total"    : fixed_total,
        "variable_total" : variable_total,
        "overall_total"  : overall_total,
        "bar_data"       : bar_data,
        "line_labels"    : line_labels,
        "line_data"      : line_data,
    })


# ── CHATBOT ───────────────────────────────────────────────────────────────────

@app.route('/chat', methods=['POST'])
def chat():
    if login_required():
        return jsonify({"error": "Unauthorized"}), 401

    msg      = (request.json or {}).get('message', '').lower().strip()
    fixed    = FixedCost.query.first()
    variable = VariableCost.query.all()
    eb_last  = ElectricityBoard.query.order_by(ElectricityBoard.id.desc()).first()
    details  = ExpenseDetails.query.all()

    fixed_total    = fixed.total if fixed else 0
    variable_total = sum(v.total for v in variable)
    overall        = fixed_total + variable_total

    if any(w in msg for w in ['total', 'overall', 'sum', 'எவ்வளவு']):
        reply = f"📊 Total: ₹{overall:,.2f}\n• Fixed: ₹{fixed_total:,.2f}\n• Variable: ₹{variable_total:,.2f}"
    elif any(w in msg for w in ['rent', 'வாடகை']):
        reply = f"🏠 Rent: ₹{fixed.rent or 0:,.2f}" if fixed else "Data இல்ல!"
    elif any(w in msg for w in ['electricity', 'eb', 'current', 'மின்சாரம்']):
        if eb_last:
            reply = f"⚡ Electricity\n• Latest: {eb_last.meter_reading} units\n• Total units: {eb_last.total_units}\n• Total cost: ₹{eb_last.total_cost:,.2f}"
        else:
            reply = "Electricity data இல்ல!"
    elif any(w in msg for w in ['provision', 'grocery', 'கடை']):
        t = sum(d.provisions_cost or 0 for d in details)
        reply = f"🛒 Provisions total: ₹{t:,.2f}"
    elif any(w in msg for w in ['vegetable', 'காய்கறி']):
        t = sum(d.vegetables_cost or 0 for d in details)
        reply = f"🥦 Vegetables: ₹{t:,.2f}"
    elif any(w in msg for w in ['transport', 'travel', 'பஸ்', 'auto']):
        t = sum(d.transport_cost or 0 for d in details)
        reply = f"🚌 Transport: ₹{t:,.2f}"
    elif any(w in msg for w in ['wifi', 'internet']):
        reply = f"📶 WiFi: ₹{fixed.wifi or 0:,.2f}" if fixed else "Data இல்ல!"
    elif any(w in msg for w in ['gas', 'cylinder']):
        reply = f"🔥 Gas: ₹{fixed.gas or 0:,.2f}" if fixed else "Data இல்ல!"
    elif any(w in msg for w in ['today', 'இன்று']):
        today_entries = [v for v in variable if v.date == date.today()]
        t = sum(v.total for v in today_entries)
        reply = f"📅 Today: ₹{t:,.2f}" if today_entries else "இன்னைக்கு entry இல்ல!"
    elif any(w in msg for w in ['month', 'மாதம்']):
        today = date.today()
        t = sum(v.total for v in variable if v.date and v.date.month == today.month and v.date.year == today.year)
        reply = f"📆 This month: ₹{t:,.2f}"
    elif any(w in msg for w in ['hi', 'hello', 'வணக்கம்', 'help']):
        reply = "👋 வணக்கம்! கேளுங்க:\n• total / overall\n• rent / வாடகை\n• electricity / மின்சாரம்\n• today / இன்று\n• month / மாதம்\n• wifi, gas, transport"
    else:
        reply = "💡 புரியல! Try: 'total', 'rent', 'electricity', 'today', 'month'"

    return jsonify({"reply": reply})


# ── RUN ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
