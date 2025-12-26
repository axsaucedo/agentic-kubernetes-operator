package controllers

import (
	"context"

	"k8s.io/apimachinery/pkg/runtime"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/log"

	agenticv1alpha1 "agentic.example.com/agentic-operator/api/v1alpha1"
)

// ModelAPIReconciler reconciles a ModelAPI object
type ModelAPIReconciler struct {
	client.Client
	Log    ctrl.Logger
	Scheme *runtime.Scheme
}

//+kubebuilder:rbac:groups=agentic.example.com,resources=modelapis,verbs=get;list;watch;create;update;patch;delete
//+kubebuilder:rbac:groups=agentic.example.com,resources=modelapis/status,verbs=get;update;patch
//+kubebuilder:rbac:groups=agentic.example.com,resources=modelapis/finalizers,verbs=update
//+kubebuilder:rbac:groups=apps,resources=deployments,verbs=get;list;watch;create;update;patch;delete
//+kubebuilder:rbac:groups="",resources=services,verbs=get;list;watch;create;update;patch;delete

// Reconcile is part of the main kubernetes reconciliation loop which aims to
// move the current state of the cluster closer to the desired state.
func (r *ModelAPIReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	log := log.FromContext(ctx)

	modelapi := &agenticv1alpha1.ModelAPI{}
	if err := r.Get(ctx, req.NamespacedName, modelapi); err != nil {
		log.Error(err, "unable to fetch ModelAPI")
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}

	// TODO: Implement ModelAPI reconciliation
	// - Create Deployment based on spec.mode (Proxy or Hosted)
	// - Create Service exposing the model API
	// - Inject environment variables
	// - Update status

	return ctrl.Result{}, nil
}

// SetupWithManager sets up the controller with the Manager.
func (r *ModelAPIReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).
		For(&agenticv1alpha1.ModelAPI{}).
		Complete(r)
}
