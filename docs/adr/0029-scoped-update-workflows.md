# Scoped Update workflows

Fortress models routine maintenance as four separate operator workflows: Host Update, Template Update, VM Update, and Service Update. Each workflow keeps a narrow target scope, composes the existing convergence or deploy ceremony for that target, and treats dependent entities as impacted dependents rather than implicit update targets; this favors explicit blast-radius control over a generic update-all workflow that would hide reboot, rebuild, and restart decisions behind one command.
