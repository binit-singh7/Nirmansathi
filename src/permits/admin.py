from django.contrib import admin
from .models import PermitApplication, ApplicationDocument, PermitDecision

class ApplicationDocumentInline(admin.TabularInline):
    model = ApplicationDocument
    extra = 1

class PermitDecisionInline(admin.StackedInline):
    model = PermitDecision
    extra = 0
    readonly_fields = ('decision_date',)

@admin.register(PermitApplication)
class PermitApplicationAdmin(admin.ModelAdmin):
    list_display = ('reference_number', 'applicant', 'application_type', 'municipality', 'ward', 'status', 'created_at')
    list_filter = ('status', 'application_type', 'municipality')
    search_fields = ('reference_number', 'applicant__username', 'tole_address', 'plot_number')
    inlines = [ApplicationDocumentInline, PermitDecisionInline]

@admin.register(ApplicationDocument)
class ApplicationDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'document_type', 'application', 'uploaded_at')
    list_filter = ('document_type',)

@admin.register(PermitDecision)
class PermitDecisionAdmin(admin.ModelAdmin):
    list_display = ('application', 'officer', 'decision', 'decision_date')
    list_filter = ('decision',)
