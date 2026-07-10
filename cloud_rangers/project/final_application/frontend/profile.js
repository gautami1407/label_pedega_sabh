// Health Profile JavaScript
// Handles profile editing, dynamic inputs, and data persistence

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
        
        // Uncheck "None" if any other allergy is selected
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
            // Initial state
            if (checkbox.checked) {
                card.classList.add('checked');
            }
            
            // Toggle on change
            checkbox.addEventListener('change', function() {
                if (this.type === 'checkbox') {
                    if (this.checked) {
                        card.classList.add('checked');
                    } else {
                        card.classList.remove('checked');
                    }
                } else if (this.type === 'radio') {
                    // Remove checked from all cards in the same group
                    const groupCards = document.querySelectorAll(`.checkbox-card input[name="${this.name}"]`);
                    groupCards.forEach(radio => {
                        radio.closest('.checkbox-card').classList.remove('checked');
                    });
                    // Add to current
                    if (this.checked) {
                        card.classList.add('checked');
                    }
                }
            });
            
            // Make entire card clickable
            card.addEventListener('click', function(e) {
                if (e.target !== checkbox && e.target.tagName !== 'LABEL') {
                    checkbox.click();
                }
            });
        }
    });
    
    // Profile Form Submission
    const profileForm = document.getElementById('profileForm');
    if (profileForm) {
        profileForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Collect updated profile data
            const profileData = {
                allergies: [],
                height: document.getElementById('profileHeight').value,
                weight: document.getElementById('profileWeight').value,
                age: document.getElementById('profileAge').value,
                dietaryPreference: null,
                otherAllergy: null,
                otherDiet: null,
                sensitivities: document.getElementById('sensitivities').value
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
                profileData.dietaryPreference = selectedDiet.value;
            }
            
            // Collect "other" values if applicable
            if (profileOtherAllergyCheckbox && profileOtherAllergyCheckbox.checked) {
                profileData.otherAllergy = document.getElementById('profileOtherAllergy').value;
            }
            
            if (profileOtherDietRadio && profileOtherDietRadio.checked) {
                profileData.otherDiet = document.getElementById('profileOtherDiet').value;
            }
            
            // Show loading state
            const submitBtn = this.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Saving...';
            submitBtn.disabled = true;
            
            const savePromise = (typeof saveUserProfile === 'function' && getAccessToken())
                ? saveUserProfile(profileData)
                : Promise.resolve(localStorage.setItem('healthProfile', JSON.stringify(profileData)));

            Promise.resolve(savePromise)
                .then(() => {
                    localStorage.setItem('healthProfile', JSON.stringify(profileData));
                    submitBtn.innerHTML = '<i class="bi bi-check-circle"></i> Saved!';
                    submitBtn.classList.remove('btn-primary');
                    submitBtn.classList.add('btn-success');
                    showSuccessMessage();
                    updateBMIDisplay();
                    setTimeout(() => {
                        submitBtn.innerHTML = originalText;
                        submitBtn.classList.remove('btn-success');
                        submitBtn.classList.add('btn-primary');
                        submitBtn.disabled = false;
                    }, 2000);
                })
                .catch((err) => {
                    alert(err.message || 'Failed to save profile.');
                    submitBtn.innerHTML = originalText;
                    submitBtn.disabled = false;
                });
        });
    }

    // BMI live calculation on height/weight change
    const heightInput = document.getElementById('profileHeight');
    const weightInput = document.getElementById('profileWeight');
    if (heightInput && weightInput) {
        heightInput.addEventListener('input', updateBMIDisplay);
        weightInput.addEventListener('input', updateBMIDisplay);
    }
    
    // Initial BMI display
    updateBMIDisplay();
});

// Calculate and display BMI
function updateBMIDisplay() {
    const heightInput = document.getElementById('profileHeight');
    const weightInput = document.getElementById('profileWeight');
    if (!heightInput || !weightInput) return;

    const height = parseFloat(heightInput.value);
    const weight = parseFloat(weightInput.value);

    // Find or create BMI display element
    let bmiDisplay = document.getElementById('bmi-display');
    if (!bmiDisplay) {
        bmiDisplay = document.createElement('div');
        bmiDisplay.id = 'bmi-display';
        bmiDisplay.style.cssText = 'margin-top:12px;padding:12px 20px;border-radius:12px;font-size:14px;font-weight:600;display:none;';
        // Insert after weight input's parent
        const weightParent = weightInput.closest('.mb-3') || weightInput.parentElement;
        if (weightParent) weightParent.after(bmiDisplay);
    }

    if (height > 0 && weight > 0) {
        const bmi = weight / ((height / 100) ** 2);
        let category = '';
        let color = '';
        if (bmi < 18.5) { category = 'Underweight'; color = '#f59e0b'; }
        else if (bmi < 25) { category = 'Normal weight'; color = '#10b981'; }
        else if (bmi < 30) { category = 'Overweight'; color = '#f59e0b'; }
        else { category = 'Obese'; color = '#ef4444'; }
        
        bmiDisplay.style.display = 'block';
        bmiDisplay.style.background = `${color}15`;
        bmiDisplay.style.border = `1px solid ${color}40`;
        bmiDisplay.style.color = color;
        bmiDisplay.innerHTML = `<i class="bi bi-heart-pulse-fill"></i> BMI: ${bmi.toFixed(1)} — ${category}`;
    } else {
        bmiDisplay.style.display = 'none';
    }
}

// Load existing profile data into form
async function loadProfileData() {
    if (typeof fetchUserProfile === 'function' && typeof getAccessToken === 'function' && getAccessToken()) {
        try {
            const profile = await fetchUserProfile();
            const mapped = mapProfileToLocal(profile);
            localStorage.setItem('healthProfile', JSON.stringify(mapped));
            populateProfileForm(mapped);
            return;
        } catch (e) {
            console.warn('Server profile load failed, using local cache.', e);
        }
    }

    const healthProfile = localStorage.getItem('healthProfile');
    if (healthProfile) {
        populateProfileForm(JSON.parse(healthProfile));
    }
}

function populateProfileForm(profileData) {
    if (!profileData) return;
    try {
        const profile = profileData;

        if (profile.allergies && Array.isArray(profile.allergies)) {
            profile.allergies.forEach(allergy => {
                const checkbox = document.querySelector(`input[name="allergies"][value="${allergy}"]`);
                if (checkbox) {
                    checkbox.checked = true;
                    checkbox.closest('.checkbox-card').classList.add('checked');

                    if (allergy === 'other' && profile.otherAllergy) {
                        const otherContainer = document.getElementById('profileOtherAllergyContainer');
                        const otherInput = document.getElementById('profileOtherAllergy');
                        if (otherContainer && otherInput) {
                            otherContainer.classList.add('show');
                            otherInput.value = profile.otherAllergy;
                        }
                    }
                }
            });
        }

        if (profile.height) {
            document.getElementById('profileHeight').value = profile.height;
        }
        if (profile.weight) {
            document.getElementById('profileWeight').value = profile.weight;
        }
        if (profile.age) {
            document.getElementById('profileAge').value = profile.age;
        }

        if (profile.dietaryPreference) {
            const dietRadio = document.querySelector(`input[name="dietaryPreference"][value="${profile.dietaryPreference}"]`);
            if (dietRadio) {
                dietRadio.checked = true;
                dietRadio.closest('.checkbox-card').classList.add('checked');

                if (profile.dietaryPreference === 'other' && profile.otherDiet) {
                    const otherContainer = document.getElementById('profileOtherDietContainer');
                    const otherInput = document.getElementById('profileOtherDiet');
                    if (otherContainer && otherInput) {
                        otherContainer.classList.add('show');
                        otherInput.value = profile.otherDiet;
                    }
                }
            }
        }

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

// Show success message with re-analysis note
function showSuccessMessage() {
    // Create success alert
    const alert = document.createElement('div');
    alert.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);z-index:9999;padding:16px 28px;background:#f0fdf4;border:2px solid #bbf7d0;border-radius:16px;box-shadow:0 10px 30px rgba(0,0,0,0.1);display:flex;align-items:center;gap:12px;max-width:500px;';
    alert.innerHTML = `
        <i class="bi bi-check-circle-fill" style="color:#10b981;font-size:24px;"></i>
        <div>
            <strong style="color:#166534;display:block;">Profile Updated!</strong>
            <span style="color:#15803d;font-size:13px;">Next product scan will use your updated profile for personalized warnings.</span>
        </div>
        <button onclick="this.parentElement.remove()" style="background:none;border:none;font-size:20px;cursor:pointer;color:#64748b;margin-left:8px;">×</button>
    `;
    
    document.body.appendChild(alert);
    
    // Auto-dismiss after 4 seconds
    setTimeout(() => {
        alert.style.opacity = '0';
        alert.style.transition = 'opacity 0.3s';
        setTimeout(() => alert.remove(), 300);
    }, 4000);
}

// Database Integration Comments
/*
    HEALTH PROFILE DATABASE INTEGRATION:
    
    In production, this would connect to:
    
    1. USER_HEALTH_PROFILES TABLE:
       Schema:
       - id (primary key)
       - user_id (foreign key to users table)
       - allergies (JSON array or separate allergy_mappings table)
       - height (decimal)
       - weight (decimal)
       - age (integer)
       - dietary_preference (varchar)
       - sensitivities (text)
       - created_at (timestamp)
       - updated_at (timestamp)
    
    2. API ENDPOINTS:
       - GET /api/user/profile - Fetch current profile
       - PUT /api/user/profile - Update profile
       - POST /api/user/profile/validate - Validate profile data
    
    3. PROFILE VALIDATION:
       - Server-side validation for age, height, weight ranges
       - Allergy cross-reference with known allergen database
       - Dietary preference standardization
    
    4. PERSONALIZATION ENGINE:
       - When profile updates, trigger re-calculation of:
         * Product compatibility scores
         * Personalized warnings
         * Recommended alternatives
       - Update cached user preferences
    
    5. AUDIT LOG:
       - Track profile changes in 'profile_change_history' table
       - Useful for: support, compliance, analytics
       - Schema: id, user_id, changed_field, old_value, new_value, timestamp
*/