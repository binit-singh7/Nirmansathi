from django.db import models
from django.utils.translation import gettext_lazy as _

class Province(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.PositiveIntegerField(unique=True, help_text=_("Province Number (1 to 7)"))

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"Province {self.code} - {self.name}"


class District(models.Model):
    province = models.ForeignKey(Province, on_delete=models.CASCADE, related_name='districts')
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ['name']
        unique_together = ('province', 'name')

    def __str__(self):
        return f"{self.name} ({self.province.name})"


class Municipality(models.Model):
    class TypeChoices(models.TextChoices):
        METROPOLITAN = 'METROPOLITAN', _('Metropolitan City')
        SUB_METROPOLITAN = 'SUB_METROPOLITAN', _('Sub-Metropolitan City')
        MUNICIPALITY = 'MUNICIPALITY', _('Municipality')
        RURAL_MUNICIPALITY = 'RURAL_MUNICIPALITY', _('Rural Municipality (Gaunpalika)')

    district = models.ForeignKey(District, on_delete=models.CASCADE, related_name='municipalities')
    name = models.CharField(max_length=150)
    type = models.CharField(max_length=30, choices=TypeChoices.choices, default=TypeChoices.MUNICIPALITY)

    class Meta:
        ordering = ['name']
        verbose_name_plural = "Municipalities"
        unique_together = ('district', 'name')

    def __str__(self):
        return f"{self.name} {self.get_type_display()} ({self.district.name})"


class Ward(models.Model):
    municipality = models.ForeignKey(Municipality, on_delete=models.CASCADE, related_name='wards')
    ward_number = models.PositiveIntegerField()

    class Meta:
        ordering = ['ward_number']
        unique_together = ('municipality', 'ward_number')

    def __str__(self):
        return f"Ward No. {self.ward_number}, {self.municipality.name}"
