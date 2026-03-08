{{/*
Copyright (c) Meta Platforms, Inc. and affiliates.
All rights reserved.
*/}}

{{/*
Expand the name of the chart.
*/}}
{{- define "gcm.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a fully qualified app name.
We truncate at 63 characters because some Kubernetes name fields are limited
to this length (by the DNS naming spec).
*/}}
{{- define "gcm.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "gcm.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "gcm.labels" -}}
helm.sh/chart: {{ include "gcm.chart" . }}
{{ include "gcm.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels.
*/}}
{{- define "gcm.selectorLabels" -}}
app.kubernetes.io/name: {{ include "gcm.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use.
*/}}
{{- define "gcm.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "gcm.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Container image reference.
*/}}
{{- define "gcm.image" -}}
{{- $tag := default .Chart.AppVersion .Values.monitoring.image.tag -}}
{{- printf "%s:%s" .Values.monitoring.image.repository $tag -}}
{{- end }}

{{/*
Health checks (NPD-GCM) image reference.
*/}}
{{- define "gcm.healthChecksImage" -}}
{{- $tag := default .Chart.AppVersion .Values.healthChecks.image.tag -}}
{{- printf "%s:%s" .Values.healthChecks.image.repository $tag -}}
{{- end }}
