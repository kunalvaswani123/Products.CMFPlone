/* BeforeUnload form processing */
if (!window.beforeunload) (function() {
    var BeforeUnloadHandler = function() {
        var self = this;

        this.message = window.form_modified_message ||
            "Discard changes? If you click OK, any changes you have made will be lost.";

        this.forms = [];
        this.chkId = [];
        this.chkType = new this.CheckType();
        this.handlers = [this.isAnyFormChanged];
        this.submitting = false;

        this.execute = function(event) {
            // NOTE: this handler is not jQuery-wrapped!
            // First clean out dead references to make sure we only work on
            // forms that are actually in the dom. This is needed in
            // combination with KSS and/or other dynamic replacements.
            var domforms = $('form'); 
            self.forms = $.grep(self.forms, function(form) {
                return domforms.index(form) > -1;
            });             
            
            // Now do the protection work
            if (self.submitting) return;

            var message;
            $.each(self.handlers, function(i, fn) {
                message = message || fn.apply(self);
            });
            if (message===true) message = self.message;
            if (message===false) message = undefined;
            if (event && message) event.returnValue = message;
            return message;
        }
        this.execute.tool = this;
    }
    var Class = BeforeUnloadHandler.prototype;

    // form checking code
    Class.isAnyFormChanged = function() {
        for (var i = 0; form = this.forms[i++];) {
            if (this.isElementChanged(form))
                return true;
        }
        return false;
    }
    Class.addHandler = function(fn) {
        this.handlers.push(fn);
    }
    Class.onsubmit = function() {
        var tool = window.onbeforeunload && window.onbeforeunload.tool;
        tool.submitting = true;
        // Also set this on the unlocking tool!
        // This way the tool knows we are in submitting,
        // and can prevent unlocking.
        plone.UnlockHandler.submitting = true;
    }
    Class.addForm = function(form) {
        if ($.inArray(form, this.forms) > -1) return;
        this.forms.push(form);
        $(form).submit(this.onsubmit);
        var elements = form.getElementsByTagName('input');
        // store hidden input's defaultValue to work around a moz bug
        $(form).find('input:hidden').each(function() {
            $(this).attr('originalValue', this.defaultValue);
        });
    }
    Class.addForms = function() {
        var self = this;
        $.each(arguments, function() {
            if (this.tagName.toLowerCase() == 'form')
                self.addForm(this);
            else
                self.addForms.apply(self, $(this).find('form').get());
        });
    }
    Class.removeForms = function() {
        var self = this;
        $.each(arguments, function() {
            if (this.tagName.toLowerCase() == 'form') {
                var el = this;
                self.forms = $.grep(self.forms, function(form) {
                    return form != el;
                });
                $(element).unbind('submit', self.onsubmit);
            } else
                self.removeForms.apply(self, $(this).find('form').get());
        });
    }

    Class.CheckType = function() {};
    var c = Class.CheckType.prototype;
    c.checkbox = c.radio = function(ele) {
        return ele.checked != ele.defaultChecked;
    }
    c.password = c.textarea = c.text = function(ele) {
        return ele.value != ele.defaultValue;
    }
    // hidden: cannot tell on Mozilla without special treatment
    c.hidden = function(ele) {
        var orig = $(ele).attr('originalValue');
        return orig && ($(ele).val() != orig);
    }

    c['select-one'] = function(ele) {
        for (var i = 0; opt=ele[i++];) {
            if (opt.selected != opt.defaultSelected) {
                if (i===1 && opt.selected) continue; /* maybe no default */
                return true;
            }
        }
        return false;
    }

    c['select-multiple'] = function(ele) {
        for (var i = 0; opt = ele[i++];) {
            if ( opt.selected != opt.defaultSelected)
                return true;
        }
        return false;
    }

    Class.chk_form = function(form) {
        // Find all form elements that are a) not marked as not-protected
        // or b) not a descendant of a non-protected element.
        var elems = $(form).find('> :input:not(.noUnloadProtection),' +
            ':not(.noUnloadProtection) :input:not(.noUnloadProtection)');
        for (var i = 0; element = elems.get(i++);) {
            if (this.isElementChanged(element))
                return true;
        }
        return false;
    }

    Class.isElementChanged = function(ele) {
        var method = ele.id && this.chkId[ele.id];
        if (!method && ele.type && ele.name)
            method = this.chkType[ele.type];
        if (!method && ele.tagName)
            method = this['chk_'+ele.tagName.toLowerCase()];

        return method? method.call(this, ele) : false;
    };

    // Can't use jQuery handlers here as kupu and kss rely on direct access.
    window.onbeforeunload = new BeforeUnloadHandler().execute;
    
    $(function() {
        var tool = window.onbeforeunload && window.onbeforeunload.tool;
        var content = getContentArea();
        if (tool && content)
            tool.addForms.apply(tool, $('form.enableUnloadProtection').get());
    });
})();
