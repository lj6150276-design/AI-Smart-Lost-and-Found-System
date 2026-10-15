from flask import Flask, render_template, request, redirect, url_for, session
import os
import mysql.connector

from werkzeug.security import generate_password_hash, check_password_hash

from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
from image_matcher import compare_images


# ==================================================
# FLASK APP
# ==================================================

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(
    app.root_path,
    "static",
    "uploads"
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

app.secret_key = "ai-lost-found-secret-key"


# ==================================================
# DATABASE CONNECTION
# ==================================================

def get_db_connection():

    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )


# ==================================================
# HOME
# ==================================================
@app.route("/")
def home():
    return redirect(url_for("register"))


# ==================================================
# REGISTER
# ==================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        phone = request.form["phone"]

        hashed_password = generate_password_hash(password)

        try:

            connection = get_db_connection()
            cursor = connection.cursor()

            query = """
                INSERT INTO users
                (name, email, password, phone)
                VALUES (%s, %s, %s, %s)
            """

            cursor.execute(
                query,
                (
                    name,
                    email,
                    hashed_password,
                    phone
                )
            )

            connection.commit()

            cursor.close()
            connection.close()

            return redirect(url_for("login"))

        except mysql.connector.Error as error:

            return f"Registration failed: {error}"

    return render_template("register.html")


# ==================================================
# LOGIN
# ==================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        try:

            connection = get_db_connection()

            cursor = connection.cursor(
                dictionary=True
            )

            query = """
                SELECT *
                FROM users
                WHERE email = %s
            """

            cursor.execute(
                query,
                (email,)
            )

            user = cursor.fetchone()

            cursor.close()
            connection.close()

            if user and check_password_hash(
                user["password"],
                password
            ):

                session["user_id"] = user["id"]
                session["user_name"] = user["name"]

                return redirect(
                    url_for("dashboard")
                )

            else:

                return "Invalid email or password!"

        except mysql.connector.Error as error:

            return f"Login failed: {error}"

    return render_template("login.html")


# ==================================================
# DASHBOARD
# ==================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    # ==================================================
    # STATISTICS
    # ==================================================

    cursor.execute(
        """
        SELECT COUNT(*) AS total_lost
        FROM lost_items
        WHERE user_id = %s
        """,
        (session["user_id"],)
    )

    total_lost = cursor.fetchone()["total_lost"]


    cursor.execute(
        """
        SELECT COUNT(*) AS total_found
        FROM found_items
        WHERE user_id = %s
        """,
        (session["user_id"],)
    )

    total_found = cursor.fetchone()["total_found"]


    cursor.execute(
        """
        SELECT COUNT(*) AS total_matched
        FROM lost_items
        WHERE user_id = %s
        AND status = 'Match Found'
        """,
        (session["user_id"],)
    )

    total_matched = cursor.fetchone()["total_matched"]


    cursor.execute(
        """
        SELECT COUNT(*) AS total_recovered
        FROM lost_items
        WHERE user_id = %s
        AND status = 'Recovered'
        """,
        (session["user_id"],)
    )

    total_recovered = cursor.fetchone()["total_recovered"]


    # ==================================================
    # NOTIFICATION COUNT
    # ==================================================

    unread_notifications = 0

    try:

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM notifications
            WHERE user_id = %s
            AND is_read = FALSE
            """,
            (session["user_id"],)
        )

        unread_notifications = cursor.fetchone()["total"]

    except mysql.connector.Error:

        unread_notifications = 0


    # ==================================================
    # RECENT REPORTS
    # ==================================================

    cursor.execute(
        """
        SELECT
            'Lost' AS report_type,
            id,
            item_name,
            category,
            location,
            status,
            created_at
        FROM lost_items
        WHERE user_id = %s

        UNION ALL

        SELECT
            'Found' AS report_type,
            id,
            item_name,
            category,
            location,
            status,
            created_at
        FROM found_items
        WHERE user_id = %s

        ORDER BY created_at DESC
        LIMIT 5
        """,
        (
            session["user_id"],
            session["user_id"]
        )
    )

    recent_reports = cursor.fetchall()


    cursor.close()
    connection.close()


    return render_template(
        "dashboard.html",
        name=session["user_name"],
        total_lost=total_lost,
        total_found=total_found,
        total_matched=total_matched,
        total_recovered=total_recovered,
        recent_reports=recent_reports,
        unread_notifications=unread_notifications
    )


# ==================================================
# REPORT LOST ITEM
# ==================================================

@app.route("/report-lost", methods=["GET", "POST"])
def report_lost():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    if request.method == "POST":

        item_name = request.form["item_name"]
        category = request.form["category"]
        description = request.form["description"]
        date_lost = request.form["date_lost"]
        location = request.form["location"]

        image = request.files.get("image")

        image_filename = None


        if image and image.filename:

            image_filename = image.filename

            image.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    image_filename
                )
            )


        connection = get_db_connection()

        cursor = connection.cursor()


        query = """
            INSERT INTO lost_items
            (
                user_id,
                item_name,
                category,
                description,
                date_lost,
                location,
                image
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """


        cursor.execute(
            query,
            (
                session["user_id"],
                item_name,
                category,
                description,
                date_lost,
                location,
                image_filename
            )
        )


        connection.commit()

        cursor.close()
        connection.close()


        return redirect(
            url_for("dashboard")
        )


    return render_template(
        "report_lost.html"
    )


# ==================================================
# REPORT FOUND ITEM
# ==================================================

@app.route("/report-found", methods=["GET", "POST"])
def report_found():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    if request.method == "POST":

        item_name = request.form["item_name"]
        category = request.form["category"]
        description = request.form["description"]
        date_found = request.form["date_found"]
        location = request.form["location"]

        image = request.files.get("image")

        image_filename = None


        if image and image.filename:

            image_filename = image.filename

            image.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    image_filename
                )
            )


        connection = get_db_connection()

        cursor = connection.cursor()


        query = """
            INSERT INTO found_items
            (
                user_id,
                item_name,
                category,
                description,
                date_found,
                location,
                image
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """


        cursor.execute(
            query,
            (
                session["user_id"],
                item_name,
                category,
                description,
                date_found,
                location,
                image_filename
            )
        )


        connection.commit()

        cursor.close()
        connection.close()


        return redirect(
            url_for("dashboard")
        )


    return render_template(
        "report_found.html"
    )


# ==================================================
# MY REPORTS
# ==================================================

@app.route("/my-reports")
def my_reports():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )


    query = """

        SELECT
            'Lost' AS report_type,
            id,
            item_name,
            category,
            description,
            date_lost AS report_date,
            location,
            image,
            status,
            created_at

        FROM lost_items

        WHERE user_id = %s


        UNION ALL


        SELECT
            'Found' AS report_type,
            id,
            item_name,
            category,
            description,
            date_found AS report_date,
            location,
            image,
            status,
            created_at

        FROM found_items

        WHERE user_id = %s


        ORDER BY created_at DESC

    """


    cursor.execute(
        query,
        (
            session["user_id"],
            session["user_id"]
        )
    )


    reports = cursor.fetchall()


    cursor.close()
    connection.close()


    return render_template(
        "my_reports.html",
        reports=reports
    )


# ==================================================
# SEARCH
# ==================================================

@app.route("/search")
def search():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    item_name = request.args.get(
        "item_name",
        ""
    ).strip()

    category = request.args.get(
        "category",
        ""
    ).strip()

    location = request.args.get(
        "location",
        ""
    ).strip()

    report_type = request.args.get(
        "report_type",
        ""
    ).strip()


    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )


    query = """

        SELECT
            'Lost' AS report_type,
            id,
            item_name,
            category,
            description,
            date_lost AS report_date,
            location,
            image,
            status

        FROM lost_items


        UNION ALL


        SELECT
            'Found' AS report_type,
            id,
            item_name,
            category,
            description,
            date_found AS report_date,
            location,
            image,
            status

        FROM found_items

    """


    cursor.execute(query)

    all_items = cursor.fetchall()


    cursor.close()
    connection.close()


    # ==================================================
    # APPLY FILTERS
    # ==================================================

    results = []


    for item in all_items:

        # Item name filter

        if item_name:

            if item_name.lower() not in (
                item["item_name"] or ""
            ).lower():

                continue


        # Category filter

        if category:

            if category.lower() != (
                item["category"] or ""
            ).lower():

                continue


        # Location filter

        if location:

            if location.lower() not in (
                item["location"] or ""
            ).lower():

                continue


        # Lost / Found filter

        if report_type:

            if report_type.lower() != (
                item["report_type"]
            ).lower():

                continue


        results.append(item)


    return render_template(
        "search.html",
        results=results,
        item_name=item_name,
        category=category,
        location=location,
        report_type=report_type
    )


# ==================================================
# AI SMART MATCHING
# ==================================================

@app.route("/matches")
def matches():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    lost_id = request.args.get(
        "lost_id"
    )


    if not lost_id:

        return "Lost item ID is required"


    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )


    # ==================================================
    # GET LOST ITEM
    # ==================================================

    cursor.execute(
        """
        SELECT *
        FROM lost_items
        WHERE id = %s
        """,
        (lost_id,)
    )


    lost_item = cursor.fetchone()


    if not lost_item:

        cursor.close()
        connection.close()

        return "Lost item not found"


    # ==================================================
    # GET FOUND ITEMS
    # ==================================================

    cursor.execute(
        """
        SELECT
            found_items.*,
            users.name AS found_by,
            users.phone AS found_phone

        FROM found_items

        JOIN users
            ON found_items.user_id = users.id

        WHERE found_items.status = 'Pending'
        """
    )


    found_items = cursor.fetchall()


    # ==================================================
    # MATCH LIST
    # ==================================================

    matches = []


    for found in found_items:

        # ==========================================
        # TEXT SCORE
        # ==========================================

        text_score = 0


        # ITEM NAME

        lost_name = (
            lost_item["item_name"] or ""
        ).lower()

        found_name = (
            found["item_name"] or ""
        ).lower()


        if lost_name == found_name:

            text_score += 40

        elif (
            lost_name in found_name
            or found_name in lost_name
        ):

            text_score += 25


        # CATEGORY

        lost_category = (
            lost_item["category"] or ""
        ).lower()

        found_category = (
            found["category"] or ""
        ).lower()


        if lost_category == found_category:

            text_score += 20


        # DESCRIPTION

        lost_description = (
            lost_item["description"] or ""
        ).lower()

        found_description = (
            found["description"] or ""
        ).lower()


        lost_words = set(
            lost_description.split()
        )

        found_words = set(
            found_description.split()
        )


        common_words = (
            lost_words.intersection(
                found_words
            )
        )


        if common_words:

            text_score += 20


        # LOCATION

        lost_location = (
            lost_item["location"] or ""
        ).lower()

        found_location = (
            found["location"] or ""
        ).lower()


        if lost_location == found_location:

            text_score += 20

        elif (
            lost_location in found_location
            or found_location in lost_location
        ):

            text_score += 10


        # ==========================================
        # IMAGE SCORE
        # ==========================================

        image_score = 0


        lost_image = lost_item.get(
            "image"
        )

        found_image = found.get(
            "image"
        )


        if lost_image and found_image:

            lost_image_path = os.path.join(
                app.config["UPLOAD_FOLDER"],
                lost_image
            )


            found_image_path = os.path.join(
                app.config["UPLOAD_FOLDER"],
                found_image
            )


            if (
                os.path.exists(
                    lost_image_path
                )
                and
                os.path.exists(
                    found_image_path
                )
            ):

                image_score = compare_images(
                    lost_image_path,
                    found_image_path
                )


        # ==========================================
        # FINAL SCORE
        # ==========================================

        if (
            lost_image
            and found_image
            and image_score > 0
        ):

            final_score = (
                (text_score * 0.50)
                +
                (image_score * 0.50)
            )

        else:

            final_score = text_score


        final_score = round(
            final_score,
            2
        )


        # ==========================================
        # SAVE MATCH
        # ==========================================

        if final_score >= 30:

            found["text_score"] = text_score

            found["image_score"] = round(
                image_score,
                2
            )

            found["match_score"] = final_score

            matches.append(found)


    # ==================================================
    # UPDATE LOST ITEM STATUS
    # ==================================================

    if matches:

        cursor.execute(
            """
            UPDATE lost_items

            SET status = 'Match Found'

            WHERE id = %s
            AND user_id = %s
            """,
            (
                lost_id,
                session["user_id"]
            )
        )


        connection.commit()


        lost_item["status"] = "Match Found"


        # ==================================================
        # CREATE NOTIFICATION
        # ==================================================

        try:

            for match in matches:

                message = (
                    "🤖 AI Match Found! "
                    + str(lost_item["item_name"])
                    + " may have been found by "
                    + str(match["found_by"])
                    + ". "
                    + "Contact: "
                    + str(match["found_phone"])
                )


                # Prevent duplicate notification

                cursor.execute(
                    """
                    SELECT id
                    FROM notifications
                    WHERE user_id = %s
                    AND message = %s
                    LIMIT 1
                    """,
                    (
                        session["user_id"],
                        message
                    )
                )


                existing_notification = (
                    cursor.fetchone()
                )


                if not existing_notification:

                    cursor.execute(
                        """
                        INSERT INTO notifications
                        (
                            user_id,
                            message
                        )
                        VALUES (%s, %s)
                        """,
                        (
                            session["user_id"],
                            message
                        )
                    )


                    # Save contact information

                    cursor.execute(
                        """
                        SELECT id
                        FROM match_contacts

                        WHERE lost_id = %s
                        AND found_id = %s

                        LIMIT 1
                        """,
                        (
                            lost_id,
                            match["id"]
                        )
                    )


                    existing_contact = (
                        cursor.fetchone()
                    )


                    if not existing_contact:

                        cursor.execute(
                            """
                            INSERT INTO match_contacts
                            (
                                lost_id,
                                found_id,
                                lost_user_id,
                                found_user_id
                            )
                            VALUES
                            (%s, %s, %s, %s)
                            """,
                            (
                                lost_id,
                                match["id"],
                                session["user_id"],
                                match["user_id"]
                            )
                        )


            connection.commit()

        except mysql.connector.Error:

            pass


    # ==================================================
    # HIGHEST SCORE FIRST
    # ==================================================

    matches.sort(
        key=lambda item: item["match_score"],
        reverse=True
    )


    cursor.close()
    connection.close()


    # ==================================================
    # SHOW MATCHES
    # ==================================================

    return render_template(
        "matches.html",
        lost_item=lost_item,
        matches=matches
    )


# ==================================================
# NOTIFICATIONS
# ==================================================

@app.route("/notifications")
def notifications():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )


    cursor.execute(
        """
        SELECT *
        FROM notifications
        WHERE user_id = %s
        ORDER BY created_at DESC
        """,
        (session["user_id"],)
    )


    notification_list = cursor.fetchall()


    cursor.close()
    connection.close()


    return render_template(
        "notifications.html",
        notifications=notification_list
    )


# ==================================================
# MARK NOTIFICATION AS READ
# ==================================================

@app.route("/notification-read/<int:notification_id>")
def notification_read(
    notification_id
):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    connection = get_db_connection()

    cursor = connection.cursor()


    cursor.execute(
        """
        UPDATE notifications

        SET is_read = TRUE

        WHERE id = %s
        AND user_id = %s
        """,
        (
            notification_id,
            session["user_id"]
        )
    )


    connection.commit()


    cursor.close()
    connection.close()


    return redirect(
        url_for("notifications")
    )


# ==================================================
# MARK ALL NOTIFICATIONS AS READ
# ==================================================

@app.route("/notifications/read-all")
def notifications_read_all():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    connection = get_db_connection()

    cursor = connection.cursor()


    cursor.execute(
        """
        UPDATE notifications

        SET is_read = TRUE

        WHERE user_id = %s
        """,
        (session["user_id"],)
    )


    connection.commit()


    cursor.close()
    connection.close()


    return redirect(
        url_for("notifications")
    )

# ==================================================
# CONTACT OWNER / FINDER
# ==================================================

def get_user_id_from_lost(lost_id):

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT user_id
        FROM lost_items
        WHERE id = %s
        """,
        (lost_id,)
    )

    result = cursor.fetchone()

    cursor.close()
    connection.close()

    if result:
        return result[0]

    return None


def get_user_id_from_found(found_id):

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT user_id
        FROM found_items
        WHERE id = %s
        """,
        (found_id,)
    )

    result = cursor.fetchone()

    cursor.close()
    connection.close()

    if result:
        return result[0]

    return None


@app.route("/contact-owner/<int:lost_id>/<int:found_id>")
def contact_owner(lost_id, found_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Get LOST item owner
    cursor.execute(
        """
        SELECT
            lost_items.item_name,
            lost_items.location,
            users.name AS owner_name,
            users.phone AS owner_phone,
            users.email AS owner_email
        FROM lost_items
        JOIN users
            ON lost_items.user_id = users.id
        WHERE lost_items.id = %s
        """,
        (lost_id,)
    )

    owner = cursor.fetchone()

    # Get FOUND item finder
    cursor.execute(
        """
        SELECT
            found_items.item_name,
            found_items.location,
            users.name AS finder_name,
            users.phone AS finder_phone,
            users.email AS finder_email
        FROM found_items
        JOIN users
            ON found_items.user_id = users.id
        WHERE found_items.id = %s
        """,
        (found_id,)
    )

    finder = cursor.fetchone()

    cursor.close()
    connection.close()

    if not owner or not finder:
        return "Contact information not found"

    # LOST PERSON → CONTACT FINDER
    if session["user_id"] == get_user_id_from_lost(lost_id):

        return render_template(
            "contact.html",
            contact_type="Finder",
            contact_name=finder["finder_name"],
            contact_phone=finder["finder_phone"],
            contact_email=finder["finder_email"],
            item_name=finder["item_name"],
            location=finder["location"],
            lost_id=lost_id,
            found_id=found_id
        )

    # FINDER → CONTACT LOST PERSON
    elif session["user_id"] == get_user_id_from_found(found_id):

        return render_template(
            "contact.html",
            contact_type="Owner",
            contact_name=owner["owner_name"],
            contact_phone=owner["owner_phone"],
            contact_email=owner["owner_email"],
            item_name=owner["item_name"],
            location=owner["location"],
            lost_id=lost_id,
            found_id=found_id
        )

    else:
        return "You are not authorized to view this contact information."

@app.route(
    "/mark-recovered/<int:lost_id>"
)
def mark_recovered(lost_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    connection = get_db_connection()

    cursor = connection.cursor()


    cursor.execute(
        """
        UPDATE lost_items

        SET status = 'Recovered'

        WHERE id = %s
        AND user_id = %s
        """,
        (
            lost_id,
            session["user_id"]
        )
    )


    connection.commit()


    cursor.close()
    connection.close()


    return redirect(
        url_for("my_reports")
    )


# ==================================================
# LOGOUT
# ==================================================

@app.route("/logout")
def logout():

    session.clear()


    return redirect(
        url_for("home")
    )


# ==================================================
# DATABASE TEST
# ==================================================

@app.route("/test-db")
def test_db():

    try:

        connection = get_db_connection()


        if connection.is_connected():

            connection.close()

            return (
                "Database connected successfully!"
            )


    except mysql.connector.Error as error:

        return (
            f"Database connection failed: {error}"
        )


# ==================================================
# RUN APPLICATION
# ==================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )