odoo.define('microcom_project_state_report.ClientAction', function (require) {
'use strict';

const { ComponentWrapper } = require('web.OwlCompatibility');

var concurrency = require('web.concurrency');
var core = require('web.core');
var Pager = require('web.Pager');
var AbstractAction = require('web.AbstractAction');
var Dialog = require('web.Dialog');
var field_utils = require('web.field_utils');
var session = require('web.session');

var QWeb = core.qweb;
var _t = core._t;

const defaultPagerSize = 400;

var ClientAction = AbstractAction.extend({
    contentTemplate: 'project_state',
    hasControlPanel: true,
    loadControlPanel: true,
    withSearchBar: true,
    searchMenuTypes: ['filter', 'favorite'],
/*    custom_events: _.extend({}, AbstractAction.prototype.custom_events, {
        onPagerChanged: '_onPagerChanged',
    }),*/

    events: {
        'click .o_project_state_click': 'o_project_state_click',
        'click .o_add_note': 'o_addNote',
        'click .o_project_update_show_detail': 'o_project_update_show_detail',
        'click .o_open_partner_form': 'o_open_partner_form',
        'click .o_open_project_form': 'o_open_project_form',
        'click .o_onDeleteProjectUpdate': 'o_onDeleteProjectUpdate'
    },



    init: function (parent, action) {
        this._super.apply(this, arguments);
        this.action = action;
        this.context = action.context;

        this.domain = [];
        this.companyId = false;

        this.ProjectState = false;
        this.ProjectUpdate = false;
        this.ProjectLinked = false;

        this.active_ids = [];
        this.pager = false;
        this.recordsPager = false;

        //this.mutex = new concurrency.Mutex();
        this.searchModelConfig.modelName = 'project.project';
    },

    async willStart() {
        await this._super(...arguments);
        const searchQuery = this.controlPanelProps.searchModel.get("query");
        this.domain = searchQuery.domain;
        onPagerChanged : this._onPagerChanged.bind(this);
        var def_control_panel = this._rpc({
            model: 'ir.model.data',
            method: 'check_object_reference',
            args: ['project', 'view_project_project_filter'],
            kwargs: {context: session.user_context},
        })
        .then(function (viewId) {
            self.viewId = viewId[1];
        });
        await this._getRecordIds();
        await this._getRecords();
    },

    start: async function () {
        await this._super(...arguments);
        if (this.ProjectState.length == 0) {
            this.$el.find('.o_project_state').append($(QWeb.render('project_nocontent_helper')));
        }
        //await this.renderPager();
    },

/*    start: async function () {
        await this._super(...arguments);
        if (this.ProjectState.length == 0) {
            this.$el.find('.o_project_state').append($(QWeb.render('project_nocontent_helper')));
        }*/
/*        this.$buttons = $(
            QWeb.render(
                "microcom_project_state_report.client_action.ControlProject",
                {}
            )
        );
        this.$buttons.on("click", ".o_report_my_projects", this.on_click_my_projects);
        this.$buttons.on("click", ".o_report_my_favorite", this.on_click_my_favorite);
        this.$buttons.on("click", ".o_report_refresh", this.on_click_refresh);

        this.controlPanelProps.cp_content = {
            $buttons: this.$buttons,
        };*/
        //await this.renderPager();
        //this._controlPanelWrapper.update(this.controlPanelProps);

/*    },*/

    /**
     * Create the Pager and render it. It needs the records information to determine the size.
     * It also needs the controlPanel to be rendered in order to append the pager to it.
     */

    renderPager: async function () {
        const currentMinimum = 1;
        const limit = defaultPagerSize;
        const size = this.recordsPager.length;
        this.pager = new ComponentWrapper(this, Pager, { currentMinimum, limit, size });


        await this.pager.mount(document.createDocumentFragment());

        const pagerContainer = Object.assign(document.createElement('span'), {
            className: 'o_project_state_pager float-right',
        });
        pagerContainer.appendChild(this.pager.el);
        this.$pager = pagerContainer;

        this._controlPanelWrapper.el.querySelector('.o_pager').append(pagerContainer);
    },

    loadFieldView: function (modelName, context, view_id, view_type, options) {
        // add the action_id to get favorite search correctly
        options.action_id = this.action.id;
        return this._super(...arguments);
    },

    _onPagerChanged: function (ev) {
        let { currentMinimum, limit } = ev.data;
        this.pager.update({ currentMinimum, limit });
        currentMinimum = currentMinimum - 1;
        this.active_ids = this.recordsPager.slice(currentMinimum, currentMinimum + limit).map(i => i.id);
        this._reloadContent();
    },

    o_onDeleteProjectUpdate: function (ev) {
        var self = this;
        ev.preventDefault();
        var arg = $(ev.currentTarget).data('res-id')
        var project_id =  $(ev.currentTarget).data('project-id');
        this._rpc({
            model: 'microcom.project.state',
            method: 'archive_project_update',
            args: [arg]
        }).then(function () {
               self.o_project_state_click(ev, project_id);

        });
    },

    o_open_partner_form: function (ev) {
        ev.preventDefault();
        return this.do_action({
            type: 'ir.actions.act_window',
            res_model: 'res.partner',
            res_id: $(ev.currentTarget).data('res-id'),
            views: [[false, 'form']],
            target: 'new'
        });
    },

    o_open_project_form: function (ev) {
        ev.preventDefault();
        return this.do_action({
            type: 'ir.actions.act_window',
            res_model: 'project.project',
            res_id: $(ev.currentTarget).data('res-id'),
            views: [[false, 'form']],
            target: 'new'
        });
    },

    _reloadContent: function () {
        var self = this;
        var $content = $(QWeb.render('project_state', {
            widget: {
                ProjectUpdate: self.ProjectUpdate,
                ProjectLinked: self.ProjectLinked,
                ProjectState: self.ProjectState,
            }
        }));
        return $('.o_project_state').replaceWith($content);
    },

    o_project_update_show_detail: function (ev) {
        var self = this;
        ev.preventDefault();
        var project_id =  $(ev.currentTarget).data('project-id');
        return this.do_action({
            type: 'ir.actions.act_window',
            res_model: 'project.update',
            res_id: $(ev.currentTarget).data('res-id'),
            views: [[false, 'form']],
            target: 'new',
            }, {
                on_close: function () {
                    return self.o_project_state_click(ev, project_id);
                }
            });
    },

    o_addNote: function (ev) {
        var self = this;
        ev.preventDefault();
        var id = ($(ev.currentTarget).data('res-id'));
        return this.do_action({
            type: 'ir.actions.act_window',
            res_model: 'project.update',
            views: [[false, 'form']],
            target: 'new',
            context: {
                'default_project_id': $(ev.currentTarget).data('res-id'),
            }
            }, {
                on_close: function () {
                    return self.o_project_state_click(ev ,id);
                }
            });
    },

    o_project_state_click: function (ev, project_id) {
        var self = this;
        ev.preventDefault();
        if (project_id){
            var arg = project_id
        } else {
            var arg = $(ev.currentTarget).data('res-id')
        }
        return this._rpc({
            model: 'microcom.project.state',
            method: 'get_project_update',
            args: [arg],
        }).then(function (result) {
          self.ProjectUpdate = result.project_update;
          self.ProjectLinked = result.project_linked;
          return self._reloadContent();
        });
    },

    _getRecordIds: function () {
        var self = this;
        var domain = this.domain;
        return this._rpc({
            model: 'project.project',
            method: 'search_read',
            domain: domain,
            fields: ['id'],
        }).then(function (ids) {
            self.recordsPager = ids;
            self.active_ids = ids.slice(0, defaultPagerSize).map(i => i.id);
        });
    },

    on_click_refresh: function () {
        self = this;
        this.domain = [];
        self._getRecordIds();
        self._reloadAllContent();
    },

    on_click_my_projects: function () {
        self = this;
        this.domain.push(['user_id', '=', session.uid]);
        self._getRecordIds();
        self._reloadAllContent();
    },

    on_click_my_favorite: function () {
        self = this;
        this.domain.push(['favorite_user_ids', 'in', [session.uid]]);
        self._getRecordIds();
        self._reloadAllContent();
    },

    _getRecords: function () {
        var self = this;
        var domain = this.domain.concat([['id', 'in', this.active_ids]]);
        return this._rpc({
            model: 'microcom.project.state',
            method: 'get_record_view',
            args: [domain],
        }).then(function (result) {
            self.ProjectState = result.project_state;
            self.ProjectUpdate = result.project_update;
            self.ProjectLinked = result.project_linked;
            self.companyId = result.company_id;
            return result;
        });
    },

    _reloadAllContent: function () {
        var self = this;
        return this._getFilterRecord().then(function () {
            var $content = $(QWeb.render('project_state', {
                widget: {
                    ProjectState: self.ProjectState,
                    ProjectUpdate: self.ProjectUpdate,
                    ProjectLinked: self.ProjectLinked,
                    company_id: self.companyId,
                }
            }));
            $('.o_project_state').replaceWith($content);
        });
    },

    _getFilterRecord: function () {
        var self = this;
        var domain = this.domain;
        return this._rpc({
            model: 'microcom.project.state',
            method: 'get_record_view',
            args: [domain],
        }).then(function (result) {
            self.companyId = result.company_id;
            self.ProjectState = result.project_state;
            self.ProjectUpdate = result.project_update;
            self.ProjectLinked = result.project_linked;
            return result;
        });
    },

    _onSearch: async function (searchQuery) {
        this.domain = searchQuery.domain;
        await this._getRecordIds();
        //const currentMinimum = 1;
        //const limit = defaultPagerSize;
        //const size = this.recordsPager.length;
        //await this.pager.update({ currentMinimum, limit, size });
        await this._reloadAllContent();
    },

});

core.action_registry.add('project_state_client_action', ClientAction);

return ClientAction;

});
