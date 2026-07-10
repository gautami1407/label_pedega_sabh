// Health Profile JavaScript v2
// Handles profile editing, dynamic inputs, and API persistence

document.addEventListener('DOMContentLoaded', function() {
    // Load existing profile data
    loadProfileData();
    
    // Handle "Other" checkbox for allergies
    const profileOtherAllergyCheckbox = document.getElementById('profile-other-allergy');
    const profileOtherAllergyContainer = document.getElementById('profileOtherAllergyContainer');
    
    if (profileOtherAllergyCheckbox && profileOtherAllergyContainer) {
        profileOtherAllergyCheckbox.addEventListener('change', function() {
            if (this.checked) {
                profileOtherAllergyContainer.classList.add('show');
            } else {
                profileOtherAllergyContainer.classList.remove('show');
                document.getElementById('profileOtherAllergy').value = '';
            }
        });
    }
    
    // Handle "Other" radio for dietary preference
    const profileOtherDietRadio = document.getElementById('profile-other-diet');
    const profileOtherDietContainer = document.getElementById('profileOtherDietContainer');
    
    if (profileOtherDietRadio && profileOtherDietContainer) {
        const dietRadios = document.querySelectorAll('input[name="dietaryPreference"]');
        dietRadios.forEach(radio => {
            radio.addEventListener('change', function() {
                if (profileOtherDietRadio.checked) {
                    profileOtherDietContainer.classList.add('show');
                } else {
                    profileOtherDietContainer.classList.remove('show');
                    document.getElementById('profileOtherDiet').value = '';
                }
            });
        });
    }
    
    // Handle "None" checkbox logic
    const profileNoneCheckbox = document.getElementById('profile-none');
    const profileAllergyCheckboxes = document.querySelectorAll('input[name="allergies"]');
    
    if (profileNoneCheckbox) {
        profileNoneCheckbox.addEventListener('change', function() {
            if (this.checked) {
                profileAllergyCheckboxes.forEach(cb => {
                    if (cb.id !== 'profile-none') {
                        cb.checked = false;
                        cb.closest('.checkbox-card').classList.remove('checked');
                    }
                });
            }
        });
        
        profileAllergyCheckboxes.forEach(cb => {
            if (cb.id !== 'profile-none') {
                cb.addEventListener('change', function() {
                    if (this.checked && profileNoneCheckbox.checked) {
                        profileNoneCheckbox.checked = false;
                        profileNoneCheckbox.closest('.checkbox-card').classList.remove('checked');
                    }
                });
            }
        });
    }
    
    // Checkbox card styling
    const checkboxCards = document.querySelectorAll('.checkbox-card');
    checkboxCards.forEach(card => {
        const checkbox = card.querySelector('input[type="checkbox"], input[type="radio"]');
        if (checkbox) {
            if (checkbox.checked) {
                card.classList.add('checked');
            }
            
            checkbox.addEventListener('change', function() {
                if (this.type === 'checkbox') {
                    if (this.checked) {
                        card.classList.add('checked');
                    } else {
                        card.classList.remove('checked');
                    }
                } else if (this.type === 'radio') {
                    const groupCards = document.querySelectorAll(`.checkbox-card input[name="${this.name}"]`);
                    groupCards.forEach(radio => {
                        radio.closest('.checkbox-card').classList.remove('checked');
                    });
                    if (this.checked) {
                        card.classList.add('checked');
                    }
                }
            });
            
            card.addEventListener('click', function(e) {
                if (e.target !== checkbox && e.target.tagName !== 'LABEL') {
                    checkbox.click();
                }
            });
        }
    });
    
    // Profile Form Submission - Uses Backend API
    const profileForm = document.getElementById('profileForm');
    if (profileForm) {
        profileForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            // Collect updated profile data
            const profileData = {
                allergies: [],
                height: document.getElementById('profileHeight').value ? parseFloat(document.getElementById('profileHeight').value) : null,
                weight: document.getElementById('profileWeight').value ? parseFloat(document.getElementById('profileWeight').value) : null,
                age: document.getElementById('profileAge').value ? parseInt(document.getElementById('profileAge').value) : null,
                dietary_preference: null,
                other_allergy: null,
                other_diet: null,
                sensitivities: document.getElementById('sensitivities').value || null
            };
            
            // Collect allergies
            profileAllergyCheckboxes.forEach(cb => {
                if (cb.checked) {
                    profileData.allergies.push(cb.value);
                }
            });
            
            // Collect dietary preference
            const selectedDiet = document.querySelector('input[name="dietaryPreference"]:checked');
            if (selectedDiet) {
                profileData.dietary_preference = selectedDiet.value;
            }
            
            // Collect "other" values
            if (profileOtherAllergyCheckbox && profileOtherAllergyCheckbox.checked) {
                profileData.other_allergy = document.getElementById('profileOtherAllergy').value;
            }
            
            if (profileOtherDietRadio && profileOtherDietRadio.checked) {
                profileData.other_diet = document.getElementById('profileOtherDiet').value;
            }
            
            // Show loading state
            const submitBtn = this.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Saving...';
            submitBtn.disabled = true;
            
            try {
                // Try to save to backend
                await updateHealthProfileBackend(profileData);
                
                // Success feedback
                submitBtn.innerHTML = '<i class="bi bi-check-circle"></i> Saved!';
                submitBtn.classList.remove('btn-primary');
                submitBtn.classList.add('btn-success');
                
                showToast('Your health profile has been updated successfully!', 'success');
                
                // Reset button after delay
                setTimeout(() => {
                    submitBtn.innerHTML = originalText;
                    submitBtn.classList.remove('btn-success');
                    submitBtn.classList.add('btn-primary');
                    submitBtn.disabled = false;
                }, 2000);
                
            } catch (error) {
                // Fallback: store locally
                localStorage.setItem('healthProfile', JSON.stringify(profileData));
                
                submitBtn.innerHTML = '<i class="bi bi-check-circle"></i> Saved Locally';
                submitBtn.classList.remove('btn-primary');
                submitBtn.classList.add('btn-success');
                
                showToast('Profile saved locally. Connect to server for cloud sync.', 'warning');
                
                setTimeout(() => {
                    submitBtn.innerHTML = originalText;
                    submitBtn.classList.remove('btn-success');
                    submitBtn.classList.add('btn-primary');
                    submitBtn.disabled = false;
                }, 2000);
            }
        });
    }
});

// Load existing profile data into form
function loadProfileData() {
    const healthProfile = localStorage.getItem('healthProfile');
    
    if (healthProfile) {
        try {
            const profile = JSON.parse(healthProfile);
            
            // Load allergies
            if (profile.allergies && Array.isArray(profile.allergies)) {
                profile.allergies.forEach(allergy => {
                    const checkbox = document.querySelector(`input[name="allergies"][value="${allergy}"]`);
                    if (checkbox) {
                        checkbox.checked = true;
                        checkbox.closest('.checkbox-card').classList.add('checked');
                        
                        if (allergy === 'other' && profile.other_allergy) {
                            const otherContainer = document.getElementById('profileOtherAllergyContainer');
                            const otherInput = document.getElementById('profileOtherAllergy');
                            if (otherContainer && otherInput) {
                                otherContainer.classList.add('show');
                                otherInput.value = profile.other_allergy;
                            }
                        }
                    }
                });
            }
            
            // Load physical metrics
            if (profile.height) {
                document.getElementById('profileHeight').value = profile.height;
            }
            if (profile.weight) {
                document.getElementById('profileWeight').value = profile.weight;
            }
            if (profile.age) {
                document.getElementById('profileAge').value = profile.age;
            }
            
            // Load dietary preference
            if (profile.dietary_preference) {
                const dietRadio = document.querySelector(`input[name="dietaryPreference"][value="${profile.dietary_preference}"]`);
                if (dietRadio) {
                    dietRadio.checked = true;
                    dietRadio.closest('.checkbox-card').classList.add('checked');
                    
                    if (profile.dietary_preference === 'other' && profile.other_diet) {
                        const otherContainer = document.getElementById('profileOtherDietContainer');
                        const otherInput = document.getElementById('profileOtherDiet');
                        if (otherContainer && otherInput) {
                            otherContainer.classList.add('show');
                            otherInput.value = profile.other_diet;
                        }
                    }
                }
            }
            
            // Load sensitivities
            if (profile.sensitivities) {
                const sensitivitiesTextarea = document.getElementById('sensitivities');
                if (sensitivitiesTextarea) {
                    sensitivitiesTextarea.value = profile.sensitivities;
                }
            }
            
        } catch (e) {
            console.error('Error loading profile data:', e);
        }
    }
}