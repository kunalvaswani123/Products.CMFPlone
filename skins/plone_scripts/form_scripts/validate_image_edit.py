## Script (Python) "validate_image_edit"
##bind container=container
##bind context=context
##bind namespace=
##bind script=script
##bind subpath=traverse_subpath
##parameters=
##title=Validates a image edit_form contents
##
REQUEST=context.REQUEST
fv=context.portal_form_validation

form=fv.createForm()
idField=fv.createField('String', 'id', title='id', required=1, display_width=20)
form.add_field(idField)

titleField=fv.createField('String', 'title', title='title', required=0, display_width=20)
form.add_field(titleField)
errors=fv.validate(form)

filename=getattr(REQUEST['field_file'], 'filename', None)
size=context.get_size()
if not filename and not size:
    if not errors: errors={}
    errors['file']='You must upload a file'

context.validate_setupRequest(errors)
return errors


