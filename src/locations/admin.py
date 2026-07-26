from django.contrib import admin
from .models import Province, District, Municipality, Ward

class DistrictInline(admin.TabularInline):
    model = District
    extra = 1

class MunicipalityInline(admin.TabularInline):
    model = Municipality
    extra = 1

class WardInline(admin.TabularInline):
    model = Ward
    extra = 1

@admin.register(Province)
class ProvinceAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')
    inlines = [DistrictInline]

@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ('name', 'province')
    list_filter = ('province',)
    inlines = [MunicipalityInline]

@admin.register(Municipality)
class MunicipalityAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'district')
    list_filter = ('type', 'district__province', 'district')
    search_fields = ('name',)
    inlines = [WardInline]

@admin.register(Ward)
class WardAdmin(admin.ModelAdmin):
    list_display = ('ward_number', 'municipality')
    list_filter = ('municipality__district', 'municipality')
