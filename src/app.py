"""
Flask web app for browsing and managing extracted jobs.
Serves API endpoints and static frontend.
"""

# pyrefly: ignore [missing-import]
from flask import Flask, render_template, request, jsonify
from pathlib import Path
import db

app = Flask(
    __name__,
    template_folder=str(Path(__file__).parent.parent / "templates"),
    static_folder=str(Path(__file__).parent.parent / "static"),
    static_url_path="/static"
)


@app.route("/")
def index():
    """Serve homepage."""
    return render_template("index.html")


@app.route("/api/jobs", methods=["GET"])
def api_jobs():
    """Fetch jobs with optional filters."""
    try:
        company = request.args.get("company", "").strip() or None
        interested_only = request.args.get("interested", "").lower() == "1"

        jobs = db.get_jobs(company=company, interested_only=interested_only)
        return jsonify({"jobs": jobs}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stats", methods=["GET"])
def api_stats():
    """Get aggregate job statistics."""
    try:
        stats = db.get_stats()
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/<job_id>/interested", methods=["POST"])
def api_set_interested(job_id):
    """Set interested state for a job."""
    try:
        # Validate job_id is integer
        try:
            job_id_int = int(job_id)
        except ValueError:
            return jsonify({"error": "Invalid job ID format"}), 400

        # Get new state from request body
        data = request.get_json() or {}
        new_state = data.get("interested")

        # Validate interested value is None, 0, or 1
        if new_state is not None and new_state not in (0, 1):
            return jsonify({"error": "Invalid interested value"}), 400

        # Set the state and fetch result
        result = db.set_interested(job_id_int, new_state)
        if result is None:
            return jsonify({"error": "Job not found"}), 404

        return jsonify({"id": job_id_int, "interested": result}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors."""
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
