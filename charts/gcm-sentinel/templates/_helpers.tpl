{{/*
Validate sentinel.actionMode — fail fast on invalid values.
*/}}
{{- define "gcm-sentinel.validateActionMode" -}}
{{- $valid := list "recommend" "annotate" "execute" -}}
{{- if not (has .Values.sentinel.actionMode $valid) -}}
{{- fail (printf "Invalid sentinel.actionMode: %q. Must be one of: %s" .Values.sentinel.actionMode (join ", " $valid)) -}}
{{- end -}}
{{- end -}}
