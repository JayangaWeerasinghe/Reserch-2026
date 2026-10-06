def register_blueprints(app):
    from .active_learning import active_learning_bp
    from .admin import admin_bp
    from .analyze import analyze_bp
    from .auth import auth_bp
    from .cases import cases_bp
    from .expert_management import expert_management_bp
    from .expert_review import expert_review_bp
    from .finetune import finetune_bp
    from .health import health_bp
    from .media import media_bp
    from .model_candidates import model_candidates_bp
    from .user import user_bp

    for blueprint in (
        health_bp,
        analyze_bp,
        cases_bp,
        media_bp,
        expert_review_bp,
        active_learning_bp,
        model_candidates_bp,
        auth_bp,
        user_bp,
        admin_bp,
        expert_management_bp,
        finetune_bp,
    ):
        app.register_blueprint(blueprint)
