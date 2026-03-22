# Resume Generation

How to create, customize, and generate tailored resumes using recipes.

---

## Concepts

**Template** -- A .docx file with placeholder slots that define the visual layout. Created automatically when you onboard a resume.

**Recipe** -- A JSON mapping that tells the generator which content (bullets, summary, skills) goes into which template slot. Recipes point at your database content so changes propagate automatically.

**Generation** -- The process of filling a template with content from a recipe to produce a finished .docx resume.

---

## Workflow 1: Generate from an Existing Recipe

If you've already onboarded a resume, you have at least one recipe.

### List your recipes

Tell Claude:

> "What resume recipes do I have?"

This calls `list_recipes` and shows available recipes with their names, headlines, and template associations.

### Generate a resume

> "Generate a resume using recipe 1"

Claude calls `generate_resume(recipe_id=1)` and returns the path to the generated .docx file.

### Review the output

Open the .docx in Word or your preferred editor. Compare against your original to verify formatting and content accuracy.

---

## Workflow 2: Tailor a Resume for a Specific Job

This is the most common workflow. You have a job description and want a resume tailored to it.

### Step 1: Run a gap analysis

Paste the job description to Claude:

> "How well do I match this job? [paste JD text]"

Claude calls `match_jd` and returns:
- **Strong matches** -- your bullets that directly address JD requirements
- **Partial matches** -- bullets that partially cover requirements
- **Gaps** -- JD requirements you don't have bullets for
- **Coverage percentage** -- overall keyword coverage

### Step 2: Create a tailored recipe

> "Create a recipe tailored for this role at [Company Name]"

Claude uses the gap analysis results to select your strongest matching bullets, picks an appropriate summary variant, and creates a new recipe optimized for the role.

### Step 3: Review and adjust

> "Show me recipe [ID]"

Check the recipe contents. You can ask Claude to swap specific bullets:

> "In recipe [ID], replace the bullet about [topic] with something about [other topic]"

### Step 4: Generate

> "Generate a resume from recipe [ID]"

### Step 5: Save the gap analysis

> "Save the gap analysis for this application"

This stores the analysis in the database so you can reference it later during interview prep.

---

## Workflow 3: Clone and Modify a Recipe

If you have a recipe that's close to what you need:

> "Clone recipe 1 and name it 'VP Engineering - Acme Corp'"

Then modify the clone:

> "Update recipe [new ID] with headline 'Technology Executive | Engineering Leadership | Digital Transformation'"

---

## Workflow 4: Build a Recipe from Scratch

For maximum control:

### Step 1: Pick your summary

> "Get me a summary for a CTO role"

### Step 2: Search for relevant bullets

> "Search my bullets for cloud architecture"
> "Search my bullets for team leadership"
> "Search my bullets tagged with 'revenue-impact'"

### Step 3: Create the recipe

> "Create a new recipe named 'CTO - Cloud Focus' with headline 'Chief Technology Officer' using these bullets: [list IDs]"

### Step 4: Generate and review

> "Generate a resume from recipe [ID]"

---

## Managing Recipes

### Update a recipe

> "Update recipe 5 with a new headline: 'Senior VP of Engineering'"

### Deactivate a recipe

> "Deactivate recipe 3" (sets is_active to false)

### Validate a recipe

The frontend at http://localhost:5175 has a recipe validation view that checks:
- All template slots have content assigned
- Referenced bullets still exist in the database
- Summary variant exists

---

## Document Operations

### Convert to PDF

> "Convert the resume at [path] to PDF"

### Compare two versions

> "Compare my base resume with the tailored version"

### Edit text in a .docx

> "In the resume at [path], replace 'old text' with 'new text'"

---

## Tips

- Always run `check_voice` on generated content before finalizing
- Keep recipes linked to applications so you can track which resume went where
- Use `mcp_compare_docs` to verify generated resumes match expected output
- The `get_resume_data` tool lets you query raw resume data (header, education, certifications) without generating a file
