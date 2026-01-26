package util

import (
	"os"
	"strings"

	corev1 "k8s.io/api/core/v1"

	kaosv1alpha1 "github.com/axsaucedo/kaos/operator/api/v1alpha1"
)

// GetDefaultTelemetryConfig returns a TelemetryConfig from global environment variables.
// Returns nil if DEFAULT_TELEMETRY_ENABLED is not "true".
func GetDefaultTelemetryConfig() *kaosv1alpha1.TelemetryConfig {
	if os.Getenv("DEFAULT_TELEMETRY_ENABLED") != "true" {
		return nil
	}
	return &kaosv1alpha1.TelemetryConfig{
		Enabled:  true,
		Endpoint: os.Getenv("DEFAULT_TELEMETRY_ENDPOINT"),
	}
}

// MergeTelemetryConfig merges component-level telemetry config with global defaults.
// Component-level config takes precedence over global defaults.
func MergeTelemetryConfig(componentConfig *kaosv1alpha1.TelemetryConfig) *kaosv1alpha1.TelemetryConfig {
	// If component has explicit config, use it
	if componentConfig != nil {
		return componentConfig
	}
	// Otherwise fall back to global defaults
	return GetDefaultTelemetryConfig()
}

// BuildTelemetryEnvVars creates environment variables for OpenTelemetry configuration.
// Uses standard OTEL_* env vars so the SDK auto-configures.
// serviceName is used as OTEL_SERVICE_NAME (typically the CR name).
// namespace is added to OTEL_RESOURCE_ATTRIBUTES (appended to existing user values).
func BuildTelemetryEnvVars(tel *kaosv1alpha1.TelemetryConfig, serviceName, namespace string) []corev1.EnvVar {
	if tel == nil || !tel.Enabled {
		return nil
	}

	envVars := []corev1.EnvVar{
		{
			Name:  "OTEL_SDK_DISABLED",
			Value: "false",
		},
		{
			Name:  "OTEL_SERVICE_NAME",
			Value: serviceName,
		},
	}

	if tel.Endpoint != "" {
		envVars = append(envVars, corev1.EnvVar{
			Name:  "OTEL_EXPORTER_OTLP_ENDPOINT",
			Value: tel.Endpoint,
		})
	}

	// Build resource attributes - append to existing user values if OTEL_RESOURCE_ATTRIBUTES is set
	kaosAttrs := "service.namespace=" + namespace + ",kaos.resource.name=" + serviceName
	existingAttrs := os.Getenv("OTEL_RESOURCE_ATTRIBUTES")
	var finalAttrs string
	if existingAttrs != "" {
		// Append KAOS attrs to user attrs (user attrs take precedence for same keys)
		finalAttrs = existingAttrs + "," + kaosAttrs
	} else {
		finalAttrs = kaosAttrs
	}
	// Remove any duplicate trailing/leading commas
	finalAttrs = strings.Trim(finalAttrs, ",")

	envVars = append(envVars, corev1.EnvVar{
		Name:  "OTEL_RESOURCE_ATTRIBUTES",
		Value: finalAttrs,
	})

	return envVars
}
