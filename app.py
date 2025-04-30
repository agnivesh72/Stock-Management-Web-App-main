import os
import datetime

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Get id
    id = session.get("user_id")

    # Get required data
    name = db.execute("SELECT username, cash FROM users WHERE id = ?", id)
    data = db.execute("SELECT * FROM owned WHERE username = ?", name[0]["username"])
    cash = name[0]["cash"]
    stock = db.execute("SELECT SUM(totalvalue) FROM owned WHERE username = ?", name[0]["username"])

    # Calculate grand total
    if (data):
        grandtotal = cash + stock[0]["SUM(totalvalue)"]

    else:
        grandtotal = cash

    # return page
    return render_template("index.html", data=data, cash=cash, grandtotal=grandtotal, name=name)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST
    if request.method == "POST":

        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # Ensure symbol was submitted
        if not symbol:
            return apology("must provide symbol", 400)

        # Ensure shares was submitted
        elif not shares:
            return apology("must provide shares", 400)

        # Ensure shares is a positive integer
        elif not shares.isdigit() or (int(shares) <= 0):
            return apology("shares must be a positive integer", 400)

        quotes = lookup(request.form.get("symbol"))

        # Ensure symbol is valid
        if not quotes:
            return apology("invaid symbol", 400)

        # Get user id from the session, total price, get cash from users and specify action
        id = session.get("user_id")
        totalprice = float(shares) * quotes["price"]
        action = "bought"
        cash = db.execute("SELECT cash FROM users WHERE id = ?", id)
        casho = cash[0]["cash"]
        time = datetime.datetime.now()

        # Ensure user has enough cash to make the purchase
        if totalprice > casho:
            return apology("insufficient balance", 400)

        # Get the username from the users database
        name = db.execute("SELECT username FROM users WHERE id = ?", id)

        # Log the details of the transation
        db.execute("INSERT INTO transactions (username, symbol, shares, action, price, datetime) VALUES (?, ?, ?, ?, ?, ?)", name[0]["username"],
                   symbol, shares, action, totalprice, time)

        # Update users cash
        casho = casho - totalprice
        db.execute("UPDATE users SET cash = ? WHERE id = ?", casho, id)

        # Update owned table
        checksymbol = db.execute("SELECT * from owned WHERE symbol = ? AND username = ?", symbol, name[0]["username"])

        # Check if user does not own some shares of that symbol
        if len(checksymbol) != 1:
            db.execute("INSERT INTO owned (username, symbol, shares, currentprice, totalvalue) VALUES (?, ?, ?, ?, ?)", name[0]["username"],
                       symbol, shares, quotes["price"], totalprice)

        # In case user already owns some shares of the symbol
        else:
            curshares = db.execute("SELECT shares FROM owned WHERE username = ? AND symbol = ?", name[0]["username"], symbol)
            shares = int(shares) + curshares[0]["shares"]
            totalprice = float(shares) * quotes["price"]
            db.execute("UPDATE owned SET shares = ?, totalvalue = ? WHERE username = ? AND symbol = ?", shares, totalprice, name[0]["username"],
                       symbol)

        # Redirect
        return redirect("/")

    # User reached route via GET
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    id = session.get("user_id")
    name = db.execute("SELECT username FROM users WHERE id = ?", id)
    transactions = db.execute("SELECT * FROM transactions WHERE username = ?", name[0]["username"])

    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via POST
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        # Lookup the results
        quotes = lookup(request.form.get("symbol"))

        # Ensure symbol is valid
        if not quotes:
            return apology("invalid symbol", 400)

        return render_template("quoted.html", quotes=quotes)

    # User reached route via GET
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        # Ensure username was submitted
        if not username:
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 400)

        # Ensure comfirm-password was submitted
        elif not confirmation:
            return apology("must provide confirmation", 400)

        # Ensure that password and confirmation are same
        elif not (password == confirmation):
            return apology("password and confirmation must match", 400)

        # Ensure username doesn't already exists
        try:
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username,
                       generate_password_hash(password, method='pbkdf2', salt_length=16))
            return redirect("/login")

        # Return aplogy in case it does
        except:
            return apology("username already exists", 400)

    # User reached via GET
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    id = session.get("user_id")
    name = db.execute("SELECT username, cash FROM users WHERE id = ?", id)
    data = db.execute("SELECT symbol, shares FROM owned WHERE username = ?", name[0]["username"])

    # User reached route via POST
    if request.method == "POST":

        # Retrieve data
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        quotes = lookup(symbol)
        action = "sold"

        # Ensure symbol and shares were provided
        if not symbol or not shares:
            return apology("must provide symbol/shares", 400)

        elif not shares.isdigit() or (int(shares) <= 0):
            return apology("shares must be a positive integer", 400)

        sym = []

        for dat in data:
            sym.append(dat["symbol"])

        # Ensure user owns the stock
        if symbol not in sym:
            return apology("You don't own the stock", 400)

        share = db.execute("SELECT shares FROM owned WHERE username = ? AND symbol = ?", name[0]["username"], symbol)

        # Ensure that user owns enough shares of the stock
        if int(shares) > share[0]["shares"]:
            return apology("You don't own enough of the stock", 400)

        else:

            # Update user's cash
            date = datetime.datetime.now()
            cash = name[0]["cash"] + (float(shares) * quotes["price"])
            db.execute("UPDATE users SET cash = ? WHERE username = ?", cash, name[0]["username"])

            # Update transactions
            db.execute("INSERT INTO transactions (username, symbol, shares, action, price, datetime) VALUES (?, ?, ?, ?, ?, ?)",
                       name[0]["username"], symbol, shares, action, float(shares) * quotes["price"], date)

            # Update owned
            if (int(shares) == share[0]["shares"]):
                db.execute("DELETE FROM owned WHERE username = ? AND symbol = ?", name[0]["username"], symbol)

            else:
                share = share[0]["shares"] - int(shares)
                totalvalue = float(share) * quotes["price"]
                db.execute("UPDATE owned SET shares = ?, totalvalue = ? WHERE username = ? AND symbol = ?", share, totalvalue,
                           name[0]["username"], symbol)

            # Redirect to home page
            return redirect("/")

    # User reached via GET
    else:
        return render_template("sell.html", data=data)


@app.route("/addcash", methods=["GET", "POST"])
@login_required
def addcash():

    # User reached route via POST
    if request.method == "POST":

        # Retrieve information
        id = session.get("user_id")
        amount = request.form.get("amount")

        if not (amount):
            return apology("must provide amount", 400)

        elif not amount.isdigit():
            return apology("amount must be positive integer", 400)

        # Calculate balance
        cash = db.execute("SELECT cash FROM users WHERE id = ?", id)
        cash = float(amount) + float(cash[0]["cash"])

        # Update user's cash
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash, id)

        # Redirect the user to home page
        return redirect("/")

    # User reached route via GET
    else:
        return render_template("addcash.html")
